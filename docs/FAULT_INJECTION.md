# Deterministic synthetic fault injection

## Scope and safety boundary

Phase 7B adds a simulator-side engineering mechanism for validating the existing diagnostic path.
Every fault identity, magnitude, and effect is synthetic TunerOS behavior, not BMW/N54/DSC fault
fidelity. The mechanism cannot connect to a vehicle, transmit on physical CAN, modify an ECU, flash
a calibration, or issue OBD/UDS/ISO-TP requests.

```text
FaultConfiguration
       |
VehicleSimulation physical state / fault-aware sensor observation
       |
simulated DME + DSC -> unchanged RawCanFrame layouts
       |
       +-> SessionRecorder
       +-> CanExplorer
       +-> authoritative DBC -> TelemetryEngine -> DiagnosticEngine
```

`DiagnosticEngine` never receives a fault ID or configuration. Faults are observable downstream only
because they change physical state or an ECU-facing sensor value before existing CAN packing.

## Configuration and time semantics

`FaultConfiguration` contains a stable `FaultId`, an activation `SimulationTimestamp`, and an
optional deactivation `SimulationTimestamp`. Configuration is part of
`SimulationRunConfiguration`; no runtime mutation exists. The domain supports multiple different
faults simultaneously, rejects duplicate IDs, and requires deactivation strictly after activation.

A fault is active at timestamp `t` exactly when:

```text
t >= activation_time && (!deactivation_time || t < deactivation_time)
```

For a fixed-step simulation whose tick does not land on a boundary, the first state observation at
or after activation sees the fault, and the first observation at or after deactivation does not.
Configuration order cannot affect results: each unique ID sets one independent fixed effect flag.
Reset retains configuration but restores the exact initial state, clock, ECU schedules, sensor
observation, and raw-frame sequence.

## Initial catalog

| CLI ID | Type | Effect while active | Existing CAN signal | Expected diagnostic in validation |
| --- | --- | --- | --- | --- |
| `cooling-degradation` | physical/system | Coolant approaches 140 degC with a 15 s time constant | `0x502 CoolantTemperature` | `TUN-DME-001` |
| `charging-failure` | physical/system | Running voltage approaches 11.8 V with a 0.5 s time constant | `0x502 BatteryVoltage` | `TUN-DME-003` |
| `map-sensor-bias` | DME sensor | Adds +220 kPa to the ECU-observed MAP | `0x501 ManifoldPressureAbsolute` | `TUN-DME-004` |
| `front-left-wheel-speed-sensor-bias` | DSC sensor | Adds +5.0 m/s to only the observed front-left wheel | `0x521 FrontLeftWheelSpeed` | `TUN-DSC-001` |

The diagnostic mapping is validation knowledge only. No production C++ fault definition contains a
DTC code.

Cooling degradation replaces the normal coolant equilibrium/time constant only while active; it
does not assign a temperature. After removal, the unchanged 92 degC/300 s thermal response resumes.
Charging failure similarly selects a low charging target/time constant only while the engine is
running. Engine-off resting-voltage behavior remains unchanged, and normal charging evolution
resumes after removal.

MAP and wheel-speed faults are sensor faults. Canonical
`VehicleState.manifold_pressure_kpa_absolute` and
`VehicleState.vehicle_speed_meters_per_second` remain physical truth. A small stack-valued
`SensorObservation` copies
the DME-visible state and four wheel observations; only the relevant observed value is biased. DBC
source labels remain `TunerOsSimulatedDme` and `TunerOsSimulatedDsc`.

## Gateway CLI

The default remains no fault:

```powershell
tuneros_gateway_sim --scenario city --port 45800
```

One explicit fault can be configured by the Phase 7B CLI:

```powershell
tuneros_gateway_sim --scenario city --port 45800 `
  --fault charging-failure --fault-at-us 5000000 --fault-clear-at-us 15000000
```

`--fault-at-us` defaults to zero when `--fault` is present. Clear time is optional. Unknown names,
negative/non-integer timestamps, timing without a fault, duplicate `--fault`, and clear time at or
before activation are rejected. The CLI may print configuration to stderr for developers; no fault
metadata enters the gateway protocol. Scenarios and faults remain orthogonal.

## CAN, diagnostics, and replay

Fault injection changes no CAN ID, DLC, signal layout, scale, transmitter label, DBC definition, or
publication period. Existing Overview and Telemetry values, CAN Explorer frames, and Diagnostics
state therefore show effects without fault-specific frontend/backend code.

Fault runs use the unchanged version-one raw session format. Manifests and frame files contain no
fault configuration, diagnostic record, event, or freeze frame. Replay needs no C++ process and no
fault identity: recorded raw frames regenerate decoded telemetry, DTC lifecycle, event timestamps,
occurrence counts, and freeze frames exactly.

No-fault output remains the Phase 7A baseline, including the default CITY contract of 27,305 raw
frames and 93,467 decoded signal updates with no diagnostics.
