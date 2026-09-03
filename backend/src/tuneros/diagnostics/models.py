"""Immutable contracts for deterministic TunerOS synthetic diagnostics."""

from dataclasses import dataclass
from enum import StrEnum

from tuneros.can import SignalValue
from tuneros.telemetry.models import SignalKey


class DiagnosticError(ValueError):
    """Base error for diagnostic-domain operations."""


class UnknownDiagnosticCodeError(DiagnosticError):
    """Raised when a DTC code is absent from the diagnostic catalog."""


class DiagnosticClearError(DiagnosticError):
    """Raised when a DTC cannot be cleared in its current state."""


class DiagnosticStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    HISTORICAL = "historical"
    CLEARED = "cleared"


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DiagnosticEventType(StrEnum):
    CONDITION_DETECTED = "condition_detected"
    CONDITION_CLEARED = "condition_cleared"
    DTC_CONFIRMED = "dtc_confirmed"
    DTC_RECOVERED = "dtc_recovered"
    DTC_CLEARED = "dtc_cleared"


@dataclass(frozen=True, slots=True)
class DiagnosticDefinition:
    code: str
    rule_id: str
    name: str
    description: str
    severity: DiagnosticSeverity
    source_system: str
    required_signals: tuple[SignalKey, ...]
    confirmation_duration_microseconds: int
    recovery_duration_microseconds: int
    activation_description: str
    recovery_description: str


@dataclass(frozen=True, slots=True)
class DiagnosticTroubleCode:
    definition: DiagnosticDefinition
    status: DiagnosticStatus
    first_detected_timestamp_microseconds: int
    confirmed_timestamp_microseconds: int | None
    last_seen_timestamp_microseconds: int
    resolved_timestamp_microseconds: int | None
    cleared_timestamp_microseconds: int | None
    occurrence_count: int
    freeze_frame_available: bool


@dataclass(frozen=True, slots=True)
class DiagnosticEvent:
    sequence: int
    timestamp_microseconds: int
    code: str
    event_type: DiagnosticEventType
    prior_status: DiagnosticStatus | None
    new_status: DiagnosticStatus | None


@dataclass(frozen=True, slots=True)
class FreezeFrameSignal:
    key: SignalKey
    value: SignalValue
    unit: str
    source_ecu: str
    arbitration_id: int
    timestamp_microseconds: int
    telemetry_frame_sequence: int


@dataclass(frozen=True, slots=True)
class DiagnosticFreezeFrame:
    code: str
    capture_timestamp_microseconds: int
    telemetry_frame_sequence: int
    signals: tuple[FreezeFrameSignal, ...]


@dataclass(frozen=True, slots=True)
class DiagnosticSnapshot:
    observation_timestamp_microseconds: int | None
    latest_telemetry_frame_sequence: int | None
    dtcs: tuple[DiagnosticTroubleCode, ...]
    retained_event_count: int
    total_event_count: int
    latest_event_sequence: int | None
    pending_count: int
    active_count: int
    historical_count: int
    cleared_count: int
