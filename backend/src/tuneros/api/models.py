"""Explicit HTTP and WebSocket serialization contracts for telemetry domain values."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from tuneros.can import SignalValue
from tuneros.telemetry import SignalFreshness, TelemetryServiceState


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
