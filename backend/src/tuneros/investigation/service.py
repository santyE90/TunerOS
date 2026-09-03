"""Streaming, isolated analysis of canonical raw-CAN session evidence."""

from collections.abc import Iterable

from tuneros.can import CanExplorer, TunerOsDbcDecoder
from tuneros.diagnostics import DiagnosticEngine, create_default_diagnostic_catalog
from tuneros.investigation.models import (
    DEFAULT_WINDOW_AFTER_MICROSECONDS,
    DEFAULT_WINDOW_BEFORE_MICROSECONDS,
    INVESTIGATION_FORMAT_NAME,
    INVESTIGATION_FORMAT_VERSION,
    MAX_INVESTIGATION_RAW_FRAMES,
    MAX_INVESTIGATION_WINDOW_MICROSECONDS,
    MAX_SELECTED_SIGNALS,
    DiagnosticStateAtTime,
    InvestigationComparison,
    InvestigationCompatibilityError,
    InvestigationEvidenceExport,
    InvestigationLimitError,
    InvestigationQueryError,
    InvestigationResult,
    InvestigationSignalSeries,
    InvestigationSignalSummary,
    InvestigationStatistics,
    InvestigationWindow,
    SignalComparison,
)
from tuneros.session import SessionCatalog, SessionManifest
from tuneros.telemetry import SignalCatalog, SignalKey, SignalSample, TelemetryEngine


class InvestigationService:
    """Query validated session artifacts without mutating active telemetry service state."""

    def __init__(self, session_catalog: SessionCatalog | None = None) -> None:
        self._sessions = session_catalog or SessionCatalog()

    @property
    def session_catalog(self) -> SessionCatalog:
        return self._sessions

    def investigate(
        self,
        session_id: str,
        *,
        center_timestamp_microseconds: int | None = None,
        before_microseconds: int = DEFAULT_WINDOW_BEFORE_MICROSECONDS,
        after_microseconds: int = DEFAULT_WINDOW_AFTER_MICROSECONDS,
        selected_signals: Iterable[SignalKey] | None = None,
        diagnostic_code: str | None = None,
    ) -> InvestigationResult:
        reader = self._sessions.reader(session_id)
        manifest = reader.manifest
        window = _resolve_window(
            manifest,
            center_timestamp_microseconds,
            before_microseconds,
            after_microseconds,
        )
        decoder = TunerOsDbcDecoder()
        signal_catalog = SignalCatalog(decoder.database_metadata)
        diagnostic_catalog = create_default_diagnostic_catalog(signal_catalog)
        selected = _resolve_signals(
            signal_catalog,
            diagnostic_catalog,
            selected_signals,
            diagnostic_code,
        )
        engine = TelemetryEngine(signal_catalog, history_capacity=1)
        diagnostics = DiagnosticEngine(diagnostic_catalog)
        explorer = CanExplorer(decoder, capacity=1)
        series = {key: [] for key in selected}
        context: dict[SignalKey, SignalSample] = {}
        raw_frames = []
        window_events = []
        decoded_signal_updates = 0
        center_states: tuple[DiagnosticStateAtTime, ...] | None = None
        center_freeze_frames = ()

        def capture_center() -> None:
            nonlocal center_states, center_freeze_frames
            if center_states is not None:
                return
            center_states = tuple(
                DiagnosticStateAtTime(
                    rule.definition,
                    None
                    if (record := diagnostics.dtc(rule.definition.code)) is None
                    else record.status,
                    record,
                )
                for rule in diagnostic_catalog.rules
            )
            center_freeze_frames = tuple(
                frame
                for rule in diagnostic_catalog.rules
                if (frame := diagnostics.freeze_frame(rule.definition.code)) is not None
            )

        for raw_frame in reader.frames():
            timestamp = raw_frame.timestamp_microseconds
            if timestamp > window.center_timestamp_microseconds:
                capture_center()
            if timestamp > window.end_timestamp_microseconds:
                continue

            annotated = explorer.ingest(raw_frame)
            decoded = decoder.decode(raw_frame)
            samples = engine.ingest(decoded)
            generated_events = diagnostics.ingest(engine.snapshot())

            if timestamp <= window.start_timestamp_microseconds:
                for sample in samples:
                    if sample.key in series:
                        context[sample.key] = sample
            if timestamp >= window.start_timestamp_microseconds:
                if len(raw_frames) >= MAX_INVESTIGATION_RAW_FRAMES:
                    raise InvestigationLimitError(
                        f"investigation raw frame count exceeds {MAX_INVESTIGATION_RAW_FRAMES}; "
                        "request a narrower window"
                    )
                raw_frames.append(annotated)
                decoded_signal_updates += len(samples)
                for sample in samples:
                    if sample.key in series:
                        series[sample.key].append(sample)
                window_events.extend(
                    event
                    for event in generated_events
                    if event.timestamp_microseconds >= window.start_timestamp_microseconds
                )

        capture_center()
        frozen_series = tuple(
            InvestigationSignalSeries(signal_catalog.require(key), tuple(series[key]))
            for key in selected
        )
        summaries = tuple(_summarize(item) for item in frozen_series)
        ordered_context = tuple(context[key] for key in selected if key in context)
        statistics = InvestigationStatistics(
            raw_frame_count=len(raw_frames),
            decoded_signal_update_count=decoded_signal_updates,
            diagnostic_event_count=len(window_events),
            selected_signal_counts=tuple((key, len(series[key])) for key in selected),
            window_duration_microseconds=window.duration_microseconds,
        )
        if center_states is None:  # pragma: no cover - capture_center always sets this
            raise AssertionError("diagnostic center state was not captured")
        return InvestigationResult(
            session=manifest,
            window=window,
            available_signals=signal_catalog.definitions,
            selected_signals=selected,
            start_context=ordered_context,
            raw_frames=tuple(raw_frames),
            telemetry_series=frozen_series,
            signal_summaries=summaries,
            diagnostic_events=tuple(window_events),
            diagnostic_states_at_center=center_states,
            freeze_frames_at_center=center_freeze_frames,
            statistics=statistics,
        )

    def compare(
        self,
        primary_session_id: str,
        baseline_session_id: str,
        *,
        primary_center_timestamp_microseconds: int | None = None,
        baseline_center_timestamp_microseconds: int | None = None,
        before_microseconds: int = DEFAULT_WINDOW_BEFORE_MICROSECONDS,
        after_microseconds: int = DEFAULT_WINDOW_AFTER_MICROSECONDS,
        selected_signals: Iterable[SignalKey] | None = None,
        diagnostic_code: str | None = None,
    ) -> InvestigationComparison:
        primary_reader = self._sessions.reader(primary_session_id)
        baseline_reader = self._sessions.reader(baseline_session_id)
        _require_compatible(primary_reader.manifest, baseline_reader.manifest)
        primary = self.investigate(
            primary_session_id,
            center_timestamp_microseconds=primary_center_timestamp_microseconds,
            before_microseconds=before_microseconds,
            after_microseconds=after_microseconds,
            selected_signals=selected_signals,
            diagnostic_code=diagnostic_code,
        )
        requested_baseline_center = (
            primary.window.center_timestamp_microseconds
            if baseline_center_timestamp_microseconds is None
            else baseline_center_timestamp_microseconds
        )
        baseline_center = _clamp_center(baseline_reader.manifest, requested_baseline_center)
        baseline = self.investigate(
            baseline_session_id,
            center_timestamp_microseconds=baseline_center,
            before_microseconds=before_microseconds,
            after_microseconds=after_microseconds,
            selected_signals=primary.selected_signals,
            diagnostic_code=diagnostic_code,
        )
        comparisons = tuple(
            SignalComparison(
                primary_summary.key,
                primary_summary,
                baseline_summary,
                (
                    None
                    if primary_summary.mean is None or baseline_summary.mean is None
                    else primary_summary.mean - baseline_summary.mean
                ),
            )
            for primary_summary, baseline_summary in zip(
                primary.signal_summaries, baseline.signal_summaries, strict=True
            )
        )
        return InvestigationComparison(
            primary=primary,
            baseline=baseline,
            signal_comparisons=comparisons,
            diagnostic_code=diagnostic_code,
            primary_has_diagnostic_event=_has_event(primary, diagnostic_code),
            baseline_has_diagnostic_event=_has_event(baseline, diagnostic_code),
        )

    def export(
        self,
        session_id: str,
        *,
        baseline_session_id: str | None = None,
        center_timestamp_microseconds: int | None = None,
        baseline_center_timestamp_microseconds: int | None = None,
        before_microseconds: int = DEFAULT_WINDOW_BEFORE_MICROSECONDS,
        after_microseconds: int = DEFAULT_WINDOW_AFTER_MICROSECONDS,
        selected_signals: Iterable[SignalKey] | None = None,
        diagnostic_code: str | None = None,
    ) -> InvestigationEvidenceExport:
        if baseline_session_id is None:
            investigation = self.investigate(
                session_id,
                center_timestamp_microseconds=center_timestamp_microseconds,
                before_microseconds=before_microseconds,
                after_microseconds=after_microseconds,
                selected_signals=selected_signals,
                diagnostic_code=diagnostic_code,
            )
            comparison = None
        else:
            comparison = self.compare(
                session_id,
                baseline_session_id,
                primary_center_timestamp_microseconds=center_timestamp_microseconds,
                baseline_center_timestamp_microseconds=baseline_center_timestamp_microseconds,
                before_microseconds=before_microseconds,
                after_microseconds=after_microseconds,
                selected_signals=selected_signals,
                diagnostic_code=diagnostic_code,
            )
            investigation = comparison.primary
        return InvestigationEvidenceExport(
            INVESTIGATION_FORMAT_NAME,
            INVESTIGATION_FORMAT_VERSION,
            investigation,
            None if comparison is None else comparison.baseline,
            () if comparison is None else comparison.signal_comparisons,
            diagnostic_code,
            None if comparison is None else comparison.primary_has_diagnostic_event,
            None if comparison is None else comparison.baseline_has_diagnostic_event,
        )


def _resolve_window(
    manifest: SessionManifest,
    center: int | None,
    before: int,
    after: int,
) -> InvestigationWindow:
    for name, value in (("before", before), ("after", after)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise InvestigationQueryError(f"{name}_microseconds must be a non-negative integer")
    if before + after > MAX_INVESTIGATION_WINDOW_MICROSECONDS:
        raise InvestigationQueryError(
            f"total investigation window cannot exceed {MAX_INVESTIGATION_WINDOW_MICROSECONDS} us"
        )
    first = manifest.first_timestamp_microseconds
    last = manifest.last_timestamp_microseconds
    if first is None or last is None:
        raise InvestigationQueryError("empty sessions cannot be investigated")
    requested_center = (first + last) // 2 if center is None else center
    if (
        isinstance(requested_center, bool)
        or not isinstance(requested_center, int)
        or requested_center < first
        or requested_center > last
    ):
        raise InvestigationQueryError(f"center timestamp must be within [{first}, {last}]")
    return InvestigationWindow(
        requested_center_timestamp_microseconds=requested_center,
        center_timestamp_microseconds=requested_center,
        requested_before_microseconds=before,
        requested_after_microseconds=after,
        start_timestamp_microseconds=max(first, requested_center - before),
        end_timestamp_microseconds=min(last, requested_center + after),
    )


def _clamp_center(manifest: SessionManifest, center: int) -> int:
    if isinstance(center, bool) or not isinstance(center, int) or center < 0:
        raise InvestigationQueryError("baseline center timestamp must be a non-negative integer")
    first = manifest.first_timestamp_microseconds
    last = manifest.last_timestamp_microseconds
    if first is None or last is None:
        raise InvestigationQueryError("empty baseline sessions cannot be investigated")
    return min(max(center, first), last)


def _resolve_signals(signal_catalog, diagnostic_catalog, selected, diagnostic_code):
    rule = diagnostic_catalog.require(diagnostic_code) if diagnostic_code is not None else None
    if selected is None:
        keys = (
            tuple(rule.definition.required_signals)
            if rule is not None
            else tuple(
                definition.key for definition in signal_catalog.definitions[:MAX_SELECTED_SIGNALS]
            )
        )
    else:
        keys = tuple(selected)
    if not keys:
        raise InvestigationQueryError("at least one signal must be selected")
    if len(keys) > MAX_SELECTED_SIGNALS:
        raise InvestigationQueryError(f"at most {MAX_SELECTED_SIGNALS} signals may be selected")
    if len(set(keys)) != len(keys):
        raise InvestigationQueryError("selected signals must be unique")
    for key in keys:
        signal_catalog.require(key)
    return keys


def _summarize(series: InvestigationSignalSeries) -> InvestigationSignalSummary:
    values = tuple(sample.value for sample in series.samples)
    if not values:
        return InvestigationSignalSummary(
            series.definition.key, "unobserved", 0, None, None, None, None, None, ()
        )
    if all(type(value) is bool for value in values):
        distinct = tuple(dict.fromkeys(values))
        return InvestigationSignalSummary(
            series.definition.key,
            "boolean",
            len(values),
            values[0],
            values[-1],
            None,
            None,
            None,
            distinct,
        )
    numeric = tuple(float(value) for value in values)
    return InvestigationSignalSummary(
        series.definition.key,
        "numeric",
        len(numeric),
        values[0],
        values[-1],
        min(numeric),
        max(numeric),
        sum(numeric) / len(numeric),
        (),
    )


def _require_compatible(primary: SessionManifest, baseline: SessionManifest) -> None:
    differences = []
    if primary.dbc_sha256 != baseline.dbc_sha256:
        differences.append("DBC hash")
    if primary.can_network != baseline.can_network:
        differences.append("CAN network")
    if primary.vehicle_profile_id != baseline.vehicle_profile_id:
        differences.append("vehicle profile")
    if differences:
        raise InvestigationCompatibilityError(
            "baseline is incompatible with primary session: " + ", ".join(differences)
        )


def _has_event(result: InvestigationResult, code: str | None) -> bool | None:
    if code is None:
        return None
    return any(event.code == code for event in result.diagnostic_events)
