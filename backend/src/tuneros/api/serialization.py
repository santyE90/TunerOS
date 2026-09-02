"""Adapt immutable telemetry-domain values to explicit API models."""

from tuneros.api.models import (
    CanDecodedSignalResponse,
    CanExplorerFrameResponse,
    CanExplorerStatisticsResponse,
    CanFrameEventResponse,
    CanMessageStatisticsResponse,
    CanSourceStateEventResponse,
    InitialCanSnapshotEventResponse,
    InitialSnapshotEventResponse,
    MessageFrameCountResponse,
    ServiceStateEventResponse,
    SessionDetailResponse,
    SessionSummaryResponse,
    SignalDefinitionResponse,
    SignalKeyResponse,
    SignalSampleResponse,
    TelemetrySnapshotResponse,
    TelemetrySourceResponse,
    TelemetryStatisticsResponse,
    TelemetryUpdateEventResponse,
)
from tuneros.can import (
    CanExplorerFrame,
    CanExplorerSnapshot,
    CanExplorerStatistics,
    CanMessageStatistics,
)
from tuneros.session import SessionManifest
from tuneros.telemetry import (
    CanExplorerUpdate,
    SignalDefinition,
    SignalFreshness,
    SignalSample,
    TelemetryService,
    TelemetryServiceState,
    TelemetryServiceStateUpdate,
    TelemetrySnapshot,
    TelemetrySourceStatus,
    TelemetryStatistics,
    TelemetryUpdate,
)


def format_arbitration_id(arbitration_id: int) -> str:
    return f"0x{arbitration_id:03X}"


def serialize_source(source: TelemetrySourceStatus) -> TelemetrySourceResponse:
    return TelemetrySourceResponse(
        mode=source.mode,
        session_id=source.session_id,
        session_name=source.session_name,
        recording=source.recording,
        recorded_frame_count=source.recorded_frame_count,
    )


def serialize_can_frame(frame: CanExplorerFrame) -> CanExplorerFrameResponse:
    raw = frame.raw_frame
    return CanExplorerFrameResponse(
        sequence=frame.sequence,
        timestamp_microseconds=raw.timestamp_microseconds,
        arbitration_id=raw.arbitration_id,
        arbitration_id_hex=format_arbitration_id(raw.arbitration_id),
        dlc=raw.payload_length,
        payload=list(raw.payload),
        payload_hex=" ".join(f"{byte:02X}" for byte in raw.payload),
        message_name=frame.message_name,
        source_ecu=frame.source_ecu,
        expected_period_microseconds=frame.expected_period_microseconds,
        decode_status=frame.decode_status,
        decode_error=frame.decode_error,
        decoded_signals=[
            CanDecodedSignalResponse(
                signal_name=signal.signal_name,
                value=signal.value,
                unit=signal.unit,
            )
            for signal in frame.decoded_signals
        ],
    )


def serialize_can_message_statistics(
    statistics: CanMessageStatistics,
) -> CanMessageStatisticsResponse:
    return CanMessageStatisticsResponse(
        arbitration_id=statistics.arbitration_id,
        arbitration_id_hex=format_arbitration_id(statistics.arbitration_id),
        message_name=statistics.message_name,
        source_ecu=statistics.source_ecu,
        retained_frame_count=statistics.retained_frame_count,
        total_frame_count=statistics.total_frame_count,
        first_timestamp_microseconds=statistics.first_timestamp_microseconds,
        latest_timestamp_microseconds=statistics.latest_timestamp_microseconds,
        expected_period_microseconds=statistics.expected_period_microseconds,
        observed_average_period_microseconds=statistics.observed_average_period_microseconds,
        observed_frequency_hz=statistics.observed_frequency_hz,
        latest_dlc=statistics.latest_dlc,
    )


def serialize_can_statistics(
    statistics: CanExplorerStatistics, source: TelemetrySourceStatus
) -> CanExplorerStatisticsResponse:
    return CanExplorerStatisticsResponse(
        retained_frame_count=statistics.retained_frame_count,
        total_frame_count=statistics.total_frame_count,
        unique_id_count=statistics.unique_id_count,
        oldest_retained_timestamp_microseconds=(statistics.oldest_retained_timestamp_microseconds),
        newest_retained_timestamp_microseconds=(statistics.newest_retained_timestamp_microseconds),
        last_sequence=statistics.last_sequence,
        source=serialize_source(source),
    )


def serialize_initial_can_snapshot(
    snapshot: CanExplorerSnapshot,
    source: TelemetrySourceStatus,
    state: TelemetryServiceState,
) -> InitialCanSnapshotEventResponse:
    return InitialCanSnapshotEventResponse(
        frames=[serialize_can_frame(frame) for frame in snapshot.frames],
        statistics=serialize_can_statistics(snapshot.statistics, source),
        messages=[serialize_can_message_statistics(statistics) for statistics in snapshot.messages],
        service_state=state,
    )


def serialize_can_update(
    update: CanExplorerUpdate, source: TelemetrySourceStatus
) -> CanFrameEventResponse:
    return CanFrameEventResponse(
        frame=serialize_can_frame(update.frame),
        statistics=serialize_can_statistics(update.statistics, source),
        message_statistics=serialize_can_message_statistics(update.message_statistics),
    )


def serialize_can_source_state(
    update: TelemetryServiceStateUpdate, source: TelemetrySourceStatus
) -> CanSourceStateEventResponse:
    return CanSourceStateEventResponse(
        state=update.state,
        error=update.error,
        source=serialize_source(source),
    )


def serialize_definition(definition: SignalDefinition) -> SignalDefinitionResponse:
    return SignalDefinitionResponse(
        key=SignalKeyResponse(
            message_name=definition.key.message_name,
            signal_name=definition.key.signal_name,
        ),
        signal_name=definition.key.signal_name,
        message_name=definition.message_name,
        arbitration_id=definition.arbitration_id,
        arbitration_id_hex=format_arbitration_id(definition.arbitration_id),
        source_ecu=definition.source_ecu,
        unit=definition.unit,
        expected_period_microseconds=definition.expected_period_microseconds,
    )


def serialize_sample(
    sample: SignalSample, freshness: SignalFreshness | None = None
) -> SignalSampleResponse:
    return SignalSampleResponse(
        key=SignalKeyResponse(
            message_name=sample.key.message_name,
            signal_name=sample.key.signal_name,
        ),
        value=sample.value,
        timestamp_microseconds=sample.timestamp_microseconds,
        frame_sequence=sample.frame_sequence,
        arbitration_id=sample.arbitration_id,
        arbitration_id_hex=format_arbitration_id(sample.arbitration_id),
        message_name=sample.message_name,
        source_ecu=sample.source_ecu,
        unit=sample.unit,
        freshness=freshness,
    )


def serialize_statistics(
    statistics: TelemetryStatistics, service: TelemetryService
) -> TelemetryStatisticsResponse:
    names_by_id = {
        definition.arbitration_id: definition.message_name
        for definition in service.catalog.definitions
    }
    return TelemetryStatisticsResponse(
        total_frames=statistics.total_frames,
        total_signal_updates=statistics.total_signal_updates,
        latest_timestamp_microseconds=statistics.latest_timestamp_microseconds,
        last_frame_sequence=statistics.last_frame_sequence,
        frames_by_message=[
            MessageFrameCountResponse(
                arbitration_id=arbitration_id,
                arbitration_id_hex=format_arbitration_id(arbitration_id),
                message_name=names_by_id[arbitration_id],
                frames=frames,
            )
            for arbitration_id, frames in sorted(statistics.frames_by_arbitration_id.items())
        ],
    )


def serialize_snapshot(
    snapshot: TelemetrySnapshot, service: TelemetryService
) -> TelemetrySnapshotResponse:
    return TelemetrySnapshotResponse(
        observation_timestamp_microseconds=snapshot.observation_timestamp_microseconds,
        last_frame_sequence=snapshot.last_frame_sequence,
        signals=[
            serialize_sample(sample, snapshot.status(key))
            for key, sample in snapshot.samples.items()
        ],
        statistics=serialize_statistics(snapshot.statistics, service),
    )


def serialize_initial_snapshot(
    snapshot: TelemetrySnapshot, service: TelemetryService
) -> InitialSnapshotEventResponse:
    return InitialSnapshotEventResponse(snapshot=serialize_snapshot(snapshot, service))


def serialize_update(update: TelemetryUpdate) -> TelemetryUpdateEventResponse:
    return TelemetryUpdateEventResponse(
        timestamp_microseconds=update.timestamp_microseconds,
        frame_sequence=update.frame_sequence,
        arbitration_id=update.arbitration_id,
        arbitration_id_hex=format_arbitration_id(update.arbitration_id),
        message_name=update.message_name,
        source_ecu=update.source_ecu,
        signals=[
            serialize_sample(sample, freshness)
            for sample, freshness in zip(update.samples, update.freshness, strict=True)
        ],
    )


def serialize_service_state(update: TelemetryServiceStateUpdate) -> ServiceStateEventResponse:
    return ServiceStateEventResponse(state=update.state, error=update.error)


def serialize_session_summary(
    manifest: SessionManifest, *, dbc_compatible: bool
) -> SessionSummaryResponse:
    return SessionSummaryResponse(
        session_id=manifest.session_id,
        name=manifest.name,
        created_at_utc=manifest.created_at_utc,
        scenario=manifest.scenario,
        status=manifest.status,
        frame_count=manifest.frame_count,
        duration_microseconds=manifest.duration_microseconds,
        dbc_compatible=dbc_compatible,
    )


def serialize_session_detail(
    manifest: SessionManifest, *, dbc_compatible: bool
) -> SessionDetailResponse:
    if manifest.frames_sha256 is None:  # complete manifests guarantee this
        raise AssertionError("complete session must have a frame-file hash")
    return SessionDetailResponse(
        **serialize_session_summary(manifest, dbc_compatible=dbc_compatible).model_dump(),
        format_name=manifest.format_name,
        format_version=manifest.format_version,
        vehicle_profile_id=manifest.vehicle_profile_id,
        can_network=manifest.can_network,
        dbc_name=manifest.dbc_name,
        dbc_sha256=manifest.dbc_sha256,
        frames_sha256=manifest.frames_sha256,
        first_timestamp_microseconds=manifest.first_timestamp_microseconds,
        last_timestamp_microseconds=manifest.last_timestamp_microseconds,
    )
