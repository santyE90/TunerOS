"""Small inspectable condition primitives over decoded telemetry snapshots."""

from dataclasses import dataclass
from enum import StrEnum

from tuneros.telemetry.models import SignalKey, TelemetrySnapshot


class ConditionResult(StrEnum):
    NORMAL = "normal"
    VIOLATION = "violation"


def _number(snapshot: TelemetrySnapshot, key: SignalKey) -> float:
    sample = snapshot.samples[key]
    if type(sample.value) not in (int, float):
        raise TypeError(f"diagnostic signal {key} must be numeric")
    return float(sample.value)


def _boolean(snapshot: TelemetrySnapshot, key: SignalKey) -> bool:
    value = snapshot.samples[key].value
    if type(value) is not bool:
        raise TypeError(f"diagnostic signal {key} must be boolean")
    return value


@dataclass(frozen=True, slots=True)
class HighThresholdCondition:
    signal: SignalKey
    activation_above: float
    recovery_below: float

    def evaluate(self, snapshot: TelemetrySnapshot, *, active: bool) -> ConditionResult:
        threshold = self.recovery_below if active else self.activation_above
        return (
            ConditionResult.VIOLATION
            if _number(snapshot, self.signal) > threshold
            else ConditionResult.NORMAL
        )


@dataclass(frozen=True, slots=True)
class LowWhileTrueCondition:
    signal: SignalKey
    context: SignalKey
    activation_below: float
    recovery_above: float

    def evaluate(self, snapshot: TelemetrySnapshot, *, active: bool) -> ConditionResult:
        if not _boolean(snapshot, self.context):
            return ConditionResult.NORMAL
        threshold = self.recovery_above if active else self.activation_below
        return (
            ConditionResult.VIOLATION
            if _number(snapshot, self.signal) < threshold
            else ConditionResult.NORMAL
        )


@dataclass(frozen=True, slots=True)
class OutsideRangeWhileTrueCondition:
    signal: SignalKey
    context: SignalKey
    activation_minimum: float
    activation_maximum: float
    recovery_minimum: float
    recovery_maximum: float

    def evaluate(self, snapshot: TelemetrySnapshot, *, active: bool) -> ConditionResult:
        if not _boolean(snapshot, self.context):
            return ConditionResult.NORMAL
        value = _number(snapshot, self.signal)
        minimum = self.recovery_minimum if active else self.activation_minimum
        maximum = self.recovery_maximum if active else self.activation_maximum
        return (
            ConditionResult.VIOLATION
            if value < minimum or value > maximum
            else ConditionResult.NORMAL
        )


@dataclass(frozen=True, slots=True)
class SignalDisagreementCondition:
    compared_signals: tuple[SignalKey, ...]
    reference_signal: SignalKey
    activation_delta: float
    recovery_delta: float

    def evaluate(self, snapshot: TelemetrySnapshot, *, active: bool) -> ConditionResult:
        reference = _number(snapshot, self.reference_signal)
        maximum_delta = max(
            abs(_number(snapshot, signal) - reference) for signal in self.compared_signals
        )
        threshold = self.recovery_delta if active else self.activation_delta
        return ConditionResult.VIOLATION if maximum_delta > threshold else ConditionResult.NORMAL
