"""Adapt immutable telemetry-domain values to explicit API models."""

from tuneros.api.models import (
    InitialSnapshotEventResponse,
    MessageFrameCountResponse,
    ServiceStateEventResponse,
    SessionDetailResponse,
    SessionSummaryResponse,
    SignalDefinitionResponse,
    SignalKeyResponse,
    SignalSampleResponse,
    TelemetrySnapshotResponse,
    TelemetryStatisticsResponse,
    TelemetryUpdateEventResponse,
)
from tuneros.session import SessionManifest
from tuneros.telemetry import (
    SignalDefinition,
    SignalFreshness,
    SignalSample,
    TelemetryService,
    TelemetryServiceStateUpdate,
    TelemetrySnapshot,
    TelemetryStatistics,
    TelemetryUpdate,
)


def format_arbitration_id(arbitration_id: int) -> str:
    return f"0x{arbitration_id:03X}"


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
