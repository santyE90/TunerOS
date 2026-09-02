"""Immutable telemetry-domain contracts."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tuneros.can import SignalValue


class TelemetryError(ValueError):
    """Base error for deterministic telemetry aggregation."""


class TelemetrySchemaError(TelemetryError):
    """Raised when decoded input disagrees with authoritative CAN metadata."""


class OutOfOrderTelemetryError(TelemetryError):
    """Raised when live decoded frames move backward in simulation time."""


class SignalFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"


@dataclass(frozen=True, slots=True, order=True)
class SignalKey:
    """Stable signal identity independent of CAN arbitration-ID assignment."""

    message_name: str
    signal_name: str


@dataclass(frozen=True, slots=True)
class SignalSample:
    key: SignalKey
    value: SignalValue
    timestamp_microseconds: int
    frame_sequence: int
    arbitration_id: int
    message_name: str
    source_ecu: str
    unit: str


@dataclass(frozen=True, slots=True)
class TelemetryStatistics:
    total_frames: int
    total_signal_updates: int
    latest_timestamp_microseconds: int | None
    last_frame_sequence: int | None
    frames_by_arbitration_id: Mapping[int, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "frames_by_arbitration_id",
            MappingProxyType(dict(self.frames_by_arbitration_id)),
        )


@dataclass(frozen=True, slots=True)
class TelemetrySnapshot:
    observation_timestamp_microseconds: int | None
    last_frame_sequence: int | None
    samples: Mapping[SignalKey, SignalSample]
    freshness: Mapping[SignalKey, SignalFreshness]
    statistics: TelemetryStatistics

    def __post_init__(self) -> None:
        object.__setattr__(self, "samples", MappingProxyType(dict(self.samples)))
        object.__setattr__(self, "freshness", MappingProxyType(dict(self.freshness)))

    def latest(self, key: SignalKey) -> SignalSample | None:
        return self.samples.get(key)

    def status(self, key: SignalKey) -> SignalFreshness | None:
        return self.freshness.get(key)
