"""Typed raw and decoded CAN boundary contracts."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

type SignalValue = float | int | bool


@dataclass(frozen=True, slots=True)
class RawCanFrame:
    """Observed standard Classic CAN data frame using simulation time."""

    arbitration_id: int
    payload: bytes
    timestamp_microseconds: int

    def __post_init__(self) -> None:
        if isinstance(self.arbitration_id, bool) or not isinstance(self.arbitration_id, int):
            raise TypeError("arbitration_id must be an integer")
        if not 0 <= self.arbitration_id <= 0x7FF:
            raise ValueError("standard CAN arbitration_id must be in [0, 0x7FF]")
        if not isinstance(self.payload, bytes):
            raise TypeError("payload must be bytes")
        if len(self.payload) > 8:
            raise ValueError("Classic CAN payload cannot exceed 8 bytes")
        if isinstance(self.timestamp_microseconds, bool) or not isinstance(
            self.timestamp_microseconds, int
        ):
            raise TypeError("timestamp_microseconds must be an integer")
        if self.timestamp_microseconds < 0:
            raise ValueError("timestamp_microseconds cannot be negative")

    @property
    def payload_length(self) -> int:
        return len(self.payload)


@dataclass(frozen=True, slots=True)
class DecodedCanFrame:
    """Engineering-unit signals decoded from one raw CAN frame."""

    arbitration_id: int
    message_name: str
    timestamp_microseconds: int
    signals: Mapping[str, SignalValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "signals", MappingProxyType(dict(self.signals)))
