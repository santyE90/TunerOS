"""Deterministic DTC lifecycle derived only from coherent telemetry snapshots."""

from collections import deque
from dataclasses import dataclass, replace

from tuneros.diagnostics.catalog import DiagnosticCatalog, DiagnosticRule
from tuneros.diagnostics.models import (
    DiagnosticClearError,
    DiagnosticEvent,
    DiagnosticEventType,
    DiagnosticFreezeFrame,
    DiagnosticSnapshot,
    DiagnosticStatus,
    DiagnosticTroubleCode,
    FreezeFrameSignal,
    UnknownDiagnosticCodeError,
)
from tuneros.diagnostics.rules import ConditionResult
from tuneros.telemetry.models import SignalFreshness, TelemetrySnapshot

DEFAULT_DIAGNOSTIC_EVENT_CAPACITY = 1_024


@dataclass(slots=True)
class _RuleState:
    dtc: DiagnosticTroubleCode | None = None
    condition_started_timestamp_microseconds: int | None = None
    recovery_started_timestamp_microseconds: int | None = None
    pending_origin: DiagnosticStatus | None = None
    freeze_frame: DiagnosticFreezeFrame | None = None


class DiagnosticEngine:
    """Evaluate ordered synthetic rules using simulation time and decoded telemetry only."""

    def __init__(
        self,
        catalog: DiagnosticCatalog,
        event_capacity: int = DEFAULT_DIAGNOSTIC_EVENT_CAPACITY,
    ) -> None:
        if isinstance(event_capacity, bool) or not isinstance(event_capacity, int):
            raise TypeError("diagnostic event capacity must be an integer")
        if event_capacity <= 0:
            raise ValueError("diagnostic event capacity must be positive")
        self._catalog = catalog
        self._event_capacity = event_capacity
        self.reset()

    @property
    def catalog(self) -> DiagnosticCatalog:
        return self._catalog

    @property
    def event_capacity(self) -> int:
        return self._event_capacity

    def ingest(self, snapshot: TelemetrySnapshot) -> tuple[DiagnosticEvent, ...]:
        timestamp = snapshot.observation_timestamp_microseconds
        if timestamp is None:
            return ()
        if self._observation_timestamp_microseconds is not None and (
            timestamp < self._observation_timestamp_microseconds
        ):
            raise ValueError("diagnostic snapshots cannot move backward in simulation time")
        generated: list[DiagnosticEvent] = []
        self._observation_timestamp_microseconds = timestamp
        self._latest_telemetry_frame_sequence = snapshot.last_frame_sequence
        for rule in self._catalog.rules:
            generated.extend(self._evaluate_rule(rule, snapshot, timestamp))
        return tuple(generated)

    def dtcs(self, status: DiagnosticStatus | None = None) -> tuple[DiagnosticTroubleCode, ...]:
        records = tuple(
            state.dtc
            for rule in self._catalog.rules
            if (state := self._states[rule.definition.code]).dtc is not None
        )
        if status is None:
            return records
        return tuple(record for record in records if record.status is status)

    def dtc(self, code: str) -> DiagnosticTroubleCode | None:
        self._catalog.require(code)
        return self._states[code].dtc

    def events(self, limit: int | None = None) -> tuple[DiagnosticEvent, ...]:
        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise TypeError("diagnostic event limit must be an integer")
            if limit <= 0:
                raise ValueError("diagnostic event limit must be positive")
        events = tuple(self._events)
        return events if limit is None else events[-limit:]

    def freeze_frame(self, code: str) -> DiagnosticFreezeFrame | None:
        self._catalog.require(code)
        return self._states[code].freeze_frame

    def clear(self, code: str) -> DiagnosticTroubleCode:
        self._catalog.require(code)
        state = self._states[code]
        dtc = state.dtc
        if dtc is None:
            raise UnknownDiagnosticCodeError(f"diagnostic code {code!r} has no DTC record")
        if dtc.status is DiagnosticStatus.CLEARED:
            return dtc
        if dtc.status is not DiagnosticStatus.HISTORICAL:
            raise DiagnosticClearError(f"{code} cannot be cleared while {dtc.status.value}")
        timestamp = self._observation_timestamp_microseconds
        if timestamp is None:  # pragma: no cover - a record requires an observation
            raise AssertionError("diagnostic record exists without an observation timestamp")
        cleared = replace(
            dtc,
            status=DiagnosticStatus.CLEARED,
            cleared_timestamp_microseconds=timestamp,
        )
        state.dtc = cleared
        self._append_event(
            generated=None,
            timestamp=timestamp,
            code=code,
            event_type=DiagnosticEventType.DTC_CLEARED,
            prior=DiagnosticStatus.HISTORICAL,
            new=DiagnosticStatus.CLEARED,
        )
        return cleared

    def snapshot(self) -> DiagnosticSnapshot:
        dtcs = self.dtcs()
        return DiagnosticSnapshot(
            observation_timestamp_microseconds=self._observation_timestamp_microseconds,
            latest_telemetry_frame_sequence=self._latest_telemetry_frame_sequence,
            dtcs=dtcs,
            retained_event_count=len(self._events),
            total_event_count=self._next_event_sequence,
            latest_event_sequence=(
                self._next_event_sequence - 1 if self._next_event_sequence else None
            ),
            pending_count=sum(item.status is DiagnosticStatus.PENDING for item in dtcs),
            active_count=sum(item.status is DiagnosticStatus.ACTIVE for item in dtcs),
            historical_count=sum(item.status is DiagnosticStatus.HISTORICAL for item in dtcs),
            cleared_count=sum(item.status is DiagnosticStatus.CLEARED for item in dtcs),
        )

    def reset(self) -> None:
        self._states = {rule.definition.code: _RuleState() for rule in self._catalog.rules}
        self._events: deque[DiagnosticEvent] = deque(maxlen=self._event_capacity)
        self._next_event_sequence = 0
        self._observation_timestamp_microseconds: int | None = None
        self._latest_telemetry_frame_sequence: int | None = None

    def _evaluate_rule(
        self, rule: DiagnosticRule, snapshot: TelemetrySnapshot, timestamp: int
    ) -> list[DiagnosticEvent]:
        state = self._states[rule.definition.code]
        if not self._inputs_are_fresh(rule, snapshot):
            state.condition_started_timestamp_microseconds = None
            state.recovery_started_timestamp_microseconds = None
            return []
        active = state.dtc is not None and state.dtc.status is DiagnosticStatus.ACTIVE
        condition = rule.condition.evaluate(snapshot, active=active)
        if condition is ConditionResult.VIOLATION:
            state.recovery_started_timestamp_microseconds = None
            return self._handle_violation(rule, state, snapshot, timestamp)
        return self._handle_normal(rule, state, timestamp)

    @staticmethod
    def _inputs_are_fresh(rule: DiagnosticRule, snapshot: TelemetrySnapshot) -> bool:
        return all(
            key in snapshot.samples and snapshot.freshness.get(key) is SignalFreshness.FRESH
            for key in rule.definition.required_signals
        )

    def _handle_violation(
        self,
        rule: DiagnosticRule,
        state: _RuleState,
        snapshot: TelemetrySnapshot,
        timestamp: int,
    ) -> list[DiagnosticEvent]:
        generated: list[DiagnosticEvent] = []
        dtc = state.dtc
        if dtc is not None and dtc.status is DiagnosticStatus.ACTIVE:
            state.dtc = replace(dtc, last_seen_timestamp_microseconds=timestamp)
            return generated
        if dtc is None or dtc.status is not DiagnosticStatus.PENDING:
            origin = None if dtc is None else dtc.status
            state.pending_origin = origin
            state.condition_started_timestamp_microseconds = timestamp
            state.dtc = self._pending_record(rule, dtc, timestamp)
            self._append_event(
                generated,
                timestamp,
                rule.definition.code,
                DiagnosticEventType.CONDITION_DETECTED,
                origin,
                DiagnosticStatus.PENDING,
            )
        elif state.condition_started_timestamp_microseconds is None:
            state.condition_started_timestamp_microseconds = timestamp
            state.dtc = replace(dtc, last_seen_timestamp_microseconds=timestamp)
        else:
            state.dtc = replace(dtc, last_seen_timestamp_microseconds=timestamp)

        started = state.condition_started_timestamp_microseconds
        if started is None:  # pragma: no cover - established above
            raise AssertionError("pending condition has no start timestamp")
        if timestamp - started >= rule.definition.confirmation_duration_microseconds:
            pending = state.dtc
            if pending is None:  # pragma: no cover - established above
                raise AssertionError("pending condition has no DTC record")
            if state.freeze_frame is None:
                state.freeze_frame = self._capture_freeze_frame(
                    rule.definition.code, snapshot, timestamp
                )
            state.dtc = replace(
                pending,
                status=DiagnosticStatus.ACTIVE,
                confirmed_timestamp_microseconds=timestamp,
                last_seen_timestamp_microseconds=timestamp,
                resolved_timestamp_microseconds=None,
                cleared_timestamp_microseconds=None,
                occurrence_count=pending.occurrence_count + 1,
                freeze_frame_available=True,
            )
            state.condition_started_timestamp_microseconds = None
            state.pending_origin = None
            self._append_event(
                generated,
                timestamp,
                rule.definition.code,
                DiagnosticEventType.DTC_CONFIRMED,
                DiagnosticStatus.PENDING,
                DiagnosticStatus.ACTIVE,
            )
        return generated

    def _handle_normal(
        self, rule: DiagnosticRule, state: _RuleState, timestamp: int
    ) -> list[DiagnosticEvent]:
        generated: list[DiagnosticEvent] = []
        dtc = state.dtc
        state.condition_started_timestamp_microseconds = None
        if dtc is None:
            return generated
        if dtc.status is DiagnosticStatus.PENDING:
            origin = state.pending_origin
            if origin is None:
                state.dtc = None
            else:
                state.dtc = replace(dtc, status=origin)
            state.pending_origin = None
            self._append_event(
                generated,
                timestamp,
                rule.definition.code,
                DiagnosticEventType.CONDITION_CLEARED,
                DiagnosticStatus.PENDING,
                origin,
            )
            return generated
        if dtc.status is not DiagnosticStatus.ACTIVE:
            state.recovery_started_timestamp_microseconds = None
            return generated
        if state.recovery_started_timestamp_microseconds is None:
            state.recovery_started_timestamp_microseconds = timestamp
        started = state.recovery_started_timestamp_microseconds
        if timestamp - started >= rule.definition.recovery_duration_microseconds:
            state.dtc = replace(
                dtc,
                status=DiagnosticStatus.HISTORICAL,
                resolved_timestamp_microseconds=timestamp,
            )
            state.recovery_started_timestamp_microseconds = None
            self._append_event(
                generated,
                timestamp,
                rule.definition.code,
                DiagnosticEventType.DTC_RECOVERED,
                DiagnosticStatus.ACTIVE,
                DiagnosticStatus.HISTORICAL,
            )
        return generated

    @staticmethod
    def _pending_record(
        rule: DiagnosticRule, existing: DiagnosticTroubleCode | None, timestamp: int
    ) -> DiagnosticTroubleCode:
        if existing is None:
            return DiagnosticTroubleCode(
                definition=rule.definition,
                status=DiagnosticStatus.PENDING,
                first_detected_timestamp_microseconds=timestamp,
                confirmed_timestamp_microseconds=None,
                last_seen_timestamp_microseconds=timestamp,
                resolved_timestamp_microseconds=None,
                cleared_timestamp_microseconds=None,
                occurrence_count=0,
                freeze_frame_available=False,
            )
        return replace(
            existing, status=DiagnosticStatus.PENDING, last_seen_timestamp_microseconds=timestamp
        )

    @staticmethod
    def _capture_freeze_frame(
        code: str, snapshot: TelemetrySnapshot, timestamp: int
    ) -> DiagnosticFreezeFrame:
        if snapshot.last_frame_sequence is None:  # pragma: no cover - observed samples imply frame
            raise AssertionError("freeze frame requires a telemetry frame sequence")
        signals = tuple(
            FreezeFrameSignal(
                key=sample.key,
                value=sample.value,
                unit=sample.unit,
                source_ecu=sample.source_ecu,
                arbitration_id=sample.arbitration_id,
                timestamp_microseconds=sample.timestamp_microseconds,
                telemetry_frame_sequence=sample.frame_sequence,
            )
            for _, sample in sorted(snapshot.samples.items(), key=lambda item: item[0])
        )
        return DiagnosticFreezeFrame(code, timestamp, snapshot.last_frame_sequence, signals)

    def _append_event(
        self,
        generated: list[DiagnosticEvent] | None,
        timestamp: int,
        code: str,
        event_type: DiagnosticEventType,
        prior: DiagnosticStatus | None,
        new: DiagnosticStatus | None,
    ) -> DiagnosticEvent:
        event = DiagnosticEvent(
            sequence=self._next_event_sequence,
            timestamp_microseconds=timestamp,
            code=code,
            event_type=event_type,
            prior_status=prior,
            new_status=new,
        )
        self._next_event_sequence += 1
        self._events.append(event)
        if generated is not None:
            generated.append(event)
        return event
