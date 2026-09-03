"""Authoritative Phase 7A catalog of synthetic TunerOS diagnostic rules."""

from dataclasses import dataclass
from typing import Protocol

from tuneros.diagnostics.models import DiagnosticDefinition, DiagnosticSeverity
from tuneros.diagnostics.rules import (
    ConditionResult,
    HighThresholdCondition,
    LowWhileTrueCondition,
    OutsideRangeWhileTrueCondition,
    SignalDisagreementCondition,
)
from tuneros.telemetry.catalog import SignalCatalog
from tuneros.telemetry.models import SignalKey, TelemetrySnapshot

COOLANT = SignalKey("DmeThermalElectrical", "CoolantTemperature")
OIL = SignalKey("DmeThermalElectrical", "OilTemperature")
BATTERY = SignalKey("DmeThermalElectrical", "BatteryVoltage")
ENGINE_RUNNING = SignalKey("DmeFastEngine", "EngineRunning")
MANIFOLD_PRESSURE = SignalKey("DmeAirLoad", "ManifoldPressureAbsolute")
VEHICLE_SPEED = SignalKey("DscVehicleMotion", "VehicleSpeed")
FRONT_LEFT_WHEEL_SPEED = SignalKey("DscWheelSpeeds", "FrontLeftWheelSpeed")
FRONT_RIGHT_WHEEL_SPEED = SignalKey("DscWheelSpeeds", "FrontRightWheelSpeed")
REAR_LEFT_WHEEL_SPEED = SignalKey("DscWheelSpeeds", "RearLeftWheelSpeed")
REAR_RIGHT_WHEEL_SPEED = SignalKey("DscWheelSpeeds", "RearRightWheelSpeed")


class DiagnosticCondition(Protocol):
    def evaluate(self, snapshot: TelemetrySnapshot, *, active: bool) -> ConditionResult: ...


@dataclass(frozen=True, slots=True)
class DiagnosticRule:
    definition: DiagnosticDefinition
    condition: DiagnosticCondition


class DiagnosticCatalog:
    """Validated deterministic rule order and stable DTC identity."""

    def __init__(self, rules: tuple[DiagnosticRule, ...], signal_catalog: SignalCatalog) -> None:
        codes: set[str] = set()
        rule_ids: set[str] = set()
        for rule in rules:
            definition = rule.definition
            if definition.code in codes:
                raise ValueError(f"duplicate diagnostic code {definition.code}")
            if definition.rule_id in rule_ids:
                raise ValueError(f"duplicate diagnostic rule ID {definition.rule_id}")
            if definition.confirmation_duration_microseconds < 0:
                raise ValueError("diagnostic confirmation duration cannot be negative")
            if definition.recovery_duration_microseconds < 0:
                raise ValueError("diagnostic recovery duration cannot be negative")
            for key in definition.required_signals:
                signal_catalog.require(key)
            codes.add(definition.code)
            rule_ids.add(definition.rule_id)
        self._rules = rules
        self._by_code = {rule.definition.code: rule for rule in rules}

    @property
    def rules(self) -> tuple[DiagnosticRule, ...]:
        return self._rules

    def get(self, code: str) -> DiagnosticRule | None:
        return self._by_code.get(code)

    def require(self, code: str) -> DiagnosticRule:
        rule = self.get(code)
        if rule is None:
            from tuneros.diagnostics.models import UnknownDiagnosticCodeError

            raise UnknownDiagnosticCodeError(f"unknown diagnostic code {code!r}")
        return rule


def _definition(
    code: str,
    rule_id: str,
    name: str,
    description: str,
    severity: DiagnosticSeverity,
    source_system: str,
    required_signals: tuple[SignalKey, ...],
    confirmation_seconds: int,
    recovery_seconds: int,
    activation_description: str,
    recovery_description: str,
) -> DiagnosticDefinition:
    return DiagnosticDefinition(
        code=code,
        rule_id=rule_id,
        name=name,
        description=description,
        severity=severity,
        source_system=source_system,
        required_signals=required_signals,
        confirmation_duration_microseconds=confirmation_seconds * 1_000_000,
        recovery_duration_microseconds=recovery_seconds * 1_000_000,
        activation_description=activation_description,
        recovery_description=recovery_description,
    )


def create_default_diagnostic_catalog(signal_catalog: SignalCatalog) -> DiagnosticCatalog:
    """Create the five Phase 7A TunerOS assumptions; these are not BMW thresholds."""

    wheel_speeds = (
        FRONT_LEFT_WHEEL_SPEED,
        FRONT_RIGHT_WHEEL_SPEED,
        REAR_LEFT_WHEEL_SPEED,
        REAR_RIGHT_WHEEL_SPEED,
    )
    rules = (
        DiagnosticRule(
            _definition(
                "TUN-DME-001",
                "dme.coolant_temperature_high",
                "Engine coolant temperature high",
                "Decoded coolant temperature remained above the TunerOS high threshold.",
                DiagnosticSeverity.CRITICAL,
                "DME",
                (COOLANT,),
                5,
                3,
                "CoolantTemperature > 115 degC",
                "CoolantTemperature <= 110 degC",
            ),
            HighThresholdCondition(COOLANT, 115.0, 110.0),
        ),
        DiagnosticRule(
            _definition(
                "TUN-DME-002",
                "dme.oil_temperature_high",
                "Engine oil temperature high",
                "Decoded oil temperature remained above the TunerOS high threshold.",
                DiagnosticSeverity.CRITICAL,
                "DME",
                (OIL,),
                5,
                3,
                "OilTemperature > 135 degC",
                "OilTemperature <= 130 degC",
            ),
            HighThresholdCondition(OIL, 135.0, 130.0),
        ),
        DiagnosticRule(
            _definition(
                "TUN-DME-003",
                "dme.charging_voltage_low",
                "Charging voltage low while running",
                "Battery voltage remained low while decoded engine-running state was true.",
                DiagnosticSeverity.WARNING,
                "DME",
                (BATTERY, ENGINE_RUNNING),
                3,
                2,
                "EngineRunning and BatteryVoltage < 12.5 V",
                "Engine stopped or BatteryVoltage >= 13.0 V",
            ),
            LowWhileTrueCondition(BATTERY, ENGINE_RUNNING, 12.5, 13.0),
        ),
        DiagnosticRule(
            _definition(
                "TUN-DME-004",
                "dme.manifold_pressure_implausible",
                "Manifold pressure implausible",
                "Decoded absolute manifold pressure remained outside broad TunerOS bounds.",
                DiagnosticSeverity.WARNING,
                "DME",
                (MANIFOLD_PRESSURE, ENGINE_RUNNING),
                2,
                2,
                "EngineRunning and MAP outside 10..250 kPa absolute",
                "Engine stopped or MAP within 15..240 kPa absolute",
            ),
            OutsideRangeWhileTrueCondition(
                MANIFOLD_PRESSURE, ENGINE_RUNNING, 10.0, 250.0, 15.0, 240.0
            ),
        ),
        DiagnosticRule(
            _definition(
                "TUN-DSC-001",
                "dsc.wheel_speed_disagreement",
                "Wheel-speed plausibility disagreement",
                "A decoded wheel speed remained materially different from decoded vehicle speed.",
                DiagnosticSeverity.WARNING,
                "DSC",
                (*wheel_speeds, VEHICLE_SPEED),
                1,
                1,
                "Any wheel differs from VehicleSpeed by > 3.0 m/s",
                "Every wheel is within 1.5 m/s of VehicleSpeed",
            ),
            SignalDisagreementCondition(wheel_speeds, VEHICLE_SPEED, 3.0, 1.5),
        ),
    )
    return DiagnosticCatalog(rules, signal_catalog)
