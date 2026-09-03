"""Immutable contracts for bounded historical session investigation."""

from dataclasses import dataclass
from typing import Literal

from tuneros.can import CanExplorerFrame, SignalValue
from tuneros.diagnostics import (
    DiagnosticDefinition,
    DiagnosticEvent,
    DiagnosticFreezeFrame,
    DiagnosticStatus,
    DiagnosticTroubleCode,
)
from tuneros.session import SessionManifest
from tuneros.telemetry import SignalDefinition, SignalKey, SignalSample

INVESTIGATION_FORMAT_NAME = "tuneros.diagnostic_investigation"
INVESTIGATION_FORMAT_VERSION = 1
DEFAULT_WINDOW_BEFORE_MICROSECONDS = 2_000_000
DEFAULT_WINDOW_AFTER_MICROSECONDS = 2_000_000
MAX_INVESTIGATION_WINDOW_MICROSECONDS = 30_000_000
MAX_INVESTIGATION_RAW_FRAMES = 8_192
MAX_SELECTED_SIGNALS = 6


class InvestigationError(ValueError):
    """Base error for safe read-only investigation queries."""


class InvestigationQueryError(InvestigationError):
    """Raised when requested timestamps or selections are invalid."""


class InvestigationCompatibilityError(InvestigationError):
    """Raised when primary and baseline session identities are incompatible."""


class InvestigationLimitError(InvestigationError):
    """Raised rather than silently truncating canonical evidence."""


@dataclass(frozen=True, slots=True)
class InvestigationWindow:
    requested_center_timestamp_microseconds: int
    center_timestamp_microseconds: int
    requested_before_microseconds: int
    requested_after_microseconds: int
    start_timestamp_microseconds: int
    end_timestamp_microseconds: int

    @property
    def duration_microseconds(self) -> int:
        return self.end_timestamp_microseconds - self.start_timestamp_microseconds


@dataclass(frozen=True, slots=True)
class InvestigationSignalSeries:
    definition: SignalDefinition
    samples: tuple[SignalSample, ...]


@dataclass(frozen=True, slots=True)
class InvestigationSignalSummary:
    key: SignalKey
    value_type: Literal["numeric", "boolean", "unobserved"]
    observation_count: int
    first: SignalValue | None
    last: SignalValue | None
    minimum: float | None
    maximum: float | None
    mean: float | None
    distinct_values: tuple[SignalValue, ...]


@dataclass(frozen=True, slots=True)
class DiagnosticStateAtTime:
    definition: DiagnosticDefinition
    status: DiagnosticStatus | None
    record: DiagnosticTroubleCode | None


@dataclass(frozen=True, slots=True)
class InvestigationStatistics:
    raw_frame_count: int
    decoded_signal_update_count: int
    diagnostic_event_count: int
    selected_signal_counts: tuple[tuple[SignalKey, int], ...]
    window_duration_microseconds: int


@dataclass(frozen=True, slots=True)
class InvestigationResult:
    session: SessionManifest
    window: InvestigationWindow
    available_signals: tuple[SignalDefinition, ...]
    selected_signals: tuple[SignalKey, ...]
    start_context: tuple[SignalSample, ...]
    raw_frames: tuple[CanExplorerFrame, ...]
    telemetry_series: tuple[InvestigationSignalSeries, ...]
    signal_summaries: tuple[InvestigationSignalSummary, ...]
    diagnostic_events: tuple[DiagnosticEvent, ...]
    diagnostic_states_at_center: tuple[DiagnosticStateAtTime, ...]
    freeze_frames_at_center: tuple[DiagnosticFreezeFrame, ...]
    statistics: InvestigationStatistics


@dataclass(frozen=True, slots=True)
class SignalComparison:
    key: SignalKey
    primary: InvestigationSignalSummary
    baseline: InvestigationSignalSummary
    mean_difference: float | None


@dataclass(frozen=True, slots=True)
class InvestigationComparison:
    primary: InvestigationResult
    baseline: InvestigationResult
    signal_comparisons: tuple[SignalComparison, ...]
    diagnostic_code: str | None
    primary_has_diagnostic_event: bool | None
    baseline_has_diagnostic_event: bool | None


@dataclass(frozen=True, slots=True)
class InvestigationEvidenceExport:
    format_name: str
    format_version: int
    investigation: InvestigationResult
    baseline: InvestigationResult | None
    signal_comparisons: tuple[SignalComparison, ...]
    diagnostic_code: str | None
    primary_has_diagnostic_event: bool | None
    baseline_has_diagnostic_event: bool | None
