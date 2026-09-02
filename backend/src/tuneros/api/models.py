"""Explicit HTTP and WebSocket serialization contracts for telemetry domain values."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from tuneros.can import SignalValue
from tuneros.session import SessionStatus
from tuneros.telemetry import SignalFreshness, TelemetryServiceState, TelemetrySourceMode


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignalKeyResponse(ApiModel):
    message_name: str
    signal_name: str


class SignalDefinitionResponse(ApiModel):
    key: SignalKeyResponse
    signal_name: str
    message_name: str
    arbitration_id: int
    arbitration_id_hex: str
    source_ecu: str
    unit: str
    expected_period_microseconds: int


class SignalSampleResponse(ApiModel):
    key: SignalKeyResponse
    value: SignalValue
    timestamp_microseconds: int
    frame_sequence: int
    arbitration_id: int
    arbitration_id_hex: str
    message_name: str
    source_ecu: str
    unit: str
    freshness: SignalFreshness | None = None


class MessageFrameCountResponse(ApiModel):
    arbitration_id: int
    arbitration_id_hex: str
    message_name: str
    frames: int


class TelemetryStatisticsResponse(ApiModel):
    total_frames: int
    total_signal_updates: int
    latest_timestamp_microseconds: int | None
    last_frame_sequence: int | None
    frames_by_message: list[MessageFrameCountResponse]


class TelemetrySnapshotResponse(ApiModel):
    observation_timestamp_microseconds: int | None
    last_frame_sequence: int | None
    signals: list[SignalSampleResponse]
    statistics: TelemetryStatisticsResponse


class TelemetryStatusResponse(ApiModel):
    service_state: TelemetryServiceState
    gateway_connected: bool
    last_error: str | None
    latest_timestamp_microseconds: int | None
    total_frames: int
    total_signal_updates: int


class TelemetrySourceResponse(ApiModel):
    mode: TelemetrySourceMode
    session_id: str | None
    session_name: str | None
    recording: bool
    recorded_frame_count: int


class CanDecodedSignalResponse(ApiModel):
    signal_name: str
    value: SignalValue
    unit: str


class CanExplorerFrameResponse(ApiModel):
    sequence: int
    timestamp_microseconds: int
    arbitration_id: int
    arbitration_id_hex: str
    dlc: int
    payload: list[int]
    payload_hex: str
    message_name: str | None
    source_ecu: str | None
    expected_period_microseconds: int | None
    decode_status: Literal["decoded", "unknown", "error"]
    decode_error: str | None
    decoded_signals: list[CanDecodedSignalResponse]


class CanMessageStatisticsResponse(ApiModel):
    arbitration_id: int
    arbitration_id_hex: str
    message_name: str | None
    source_ecu: str | None
    retained_frame_count: int
    total_frame_count: int
    first_timestamp_microseconds: int
    latest_timestamp_microseconds: int
    expected_period_microseconds: int | None
    observed_average_period_microseconds: float | None
    observed_frequency_hz: float | None
    latest_dlc: int


class CanExplorerStatisticsResponse(ApiModel):
    retained_frame_count: int
    total_frame_count: int
    unique_id_count: int
    oldest_retained_timestamp_microseconds: int | None
    newest_retained_timestamp_microseconds: int | None
    last_sequence: int | None
    source: TelemetrySourceResponse


class InitialCanSnapshotEventResponse(ApiModel):
    type: Literal["initial_can_snapshot"] = "initial_can_snapshot"
    frames: list[CanExplorerFrameResponse]
    statistics: CanExplorerStatisticsResponse
    messages: list[CanMessageStatisticsResponse]
    service_state: TelemetryServiceState


class CanFrameEventResponse(ApiModel):
    type: Literal["can_frame"] = "can_frame"
    frame: CanExplorerFrameResponse
    statistics: CanExplorerStatisticsResponse
    message_statistics: CanMessageStatisticsResponse


class CanSourceStateEventResponse(ApiModel):
    type: Literal["can_source_state"] = "can_source_state"
    state: TelemetryServiceState
    error: str | None
    source: TelemetrySourceResponse


class SessionSummaryResponse(ApiModel):
    session_id: str
    name: str | None
    created_at_utc: str
    scenario: str | None
    status: SessionStatus
    frame_count: int
    duration_microseconds: int
    dbc_compatible: bool


class SessionDetailResponse(SessionSummaryResponse):
    format_name: str
    format_version: int
    vehicle_profile_id: str
    can_network: str
    dbc_name: str
    dbc_sha256: str
    frames_sha256: str
    first_timestamp_microseconds: int | None
    last_timestamp_microseconds: int | None


class SessionReplayResponse(ApiModel):
    session_id: str
    session_name: str | None
    source_mode: Literal["replay"] = "replay"
    service_state: Literal["running"] = "running"


class SignalResponse(ApiModel):
    definition: SignalDefinitionResponse
    sample: SignalSampleResponse | None
    freshness: SignalFreshness | None


class SignalHistoryResponse(ApiModel):
    definition: SignalDefinitionResponse
    samples: list[SignalSampleResponse]


class InitialSnapshotEventResponse(ApiModel):
    type: Literal["initial_snapshot"] = "initial_snapshot"
    snapshot: TelemetrySnapshotResponse


class TelemetryUpdateEventResponse(ApiModel):
    type: Literal["telemetry_update"] = "telemetry_update"
    timestamp_microseconds: int
    frame_sequence: int
    arbitration_id: int
    arbitration_id_hex: str
    message_name: str
    source_ecu: str
    signals: list[SignalSampleResponse]


class ServiceStateEventResponse(ApiModel):
    type: Literal["service_state"] = "service_state"
    state: TelemetryServiceState
    error: str | None = None
