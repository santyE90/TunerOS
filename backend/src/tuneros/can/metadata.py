"""Immutable TunerOS-owned views of authoritative CAN database metadata."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanSignalMetadata:
    """DBC-derived metadata for one decoded signal."""

    signal_name: str
    unit: str


@dataclass(frozen=True, slots=True)
class CanMessageMetadata:
    """DBC-derived metadata for one synthetic CAN message."""

    arbitration_id: int
    message_name: str
    transmitter: str
    cycle_time_microseconds: int
    signals: tuple[CanSignalMetadata, ...]


@dataclass(frozen=True, slots=True)
class CanDatabaseMetadata:
    """Library-independent metadata snapshot for the packaged CAN database."""

    messages: tuple[CanMessageMetadata, ...]
