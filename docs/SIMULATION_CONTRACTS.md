# Simulation contracts

This specification defines the stable engineering contracts and records the Phase 1A deterministic
IDLE implementation. Phase 1A adds only vehicle-side clock, scenario input, orchestration, and
minimal state evolution; downstream ECU/CAN and application layers remain unimplemented.

## Simulation time

**Simulation time** determines vehicle evolution. **Wall-clock time** only determines how quickly a
human observes a run. Core simulation logic must not call system clock APIs to calculate vehicle
state. It must be possible to execute 60 seconds of simulated time without waiting 60 real seconds.

The canonical `SimulationTimestamp` is an unsigned 64-bit count of **integer microseconds since the
start of the current run**. `SimulationDuration` uses the same representation. This is monotonic,
precise enough for planned signal rates, naturally excludes negative values, and avoids cumulative
floating-point drift. Conversion to floating-point seconds is permitted only for equations or at
explicit boundaries; time accumulation remains integer.

The initial base step is **10,000 µs (10 ms, 100 Hz)**, a category C TunerOS scheduling decision. It
is fast enough to teach engine-signal scheduling without pretending to reproduce DME task timing or
burdening the first simple model. Components should run on deterministic integer tick intervals:

| Example work | Effective rate | Interval in base ticks |
| --- | ---: | ---: |
| Core update and fast engine state | 100 Hz | 1 |
| Wheel-speed logic | 50 Hz | 2 |
| Thermal state | 10 Hz | 10 |

These example rates are TunerOS decisions, not BMW specifications. Components must not create
independent arbitrary timers. A requested component period must be an integer multiple of the base
step where practical; any exception requires an explicit scheduling decision.

The implemented `SimulationClock` provides these semantics:

- a new or reset run has timestamp zero and tick zero;
- one running tick advances exactly one configured fixed step;
- simulation time never moves backward within a run and must not silently overflow;
- paused or completed clocks do not advance; resume continues from the same timestamp;
- reset clears timestamp, tick count, completion state, and run-scoped deterministic state;
- scenario duration is simulation duration, and completion occurs at its specified boundary;
- a step value is immutable within one run and must be positive.

It exposes timestamp, fixed step, tick count, pause state, one/N-tick advancement, pause/resume, and
reset. Construction rejects a zero step, and advancement rejects integer timestamp overflow. It has
no wall-clock scheduling or playback-speed behavior.

## Determinism

Given identical vehicle profile, initial state, scenario, duration, step, calibration, fault
configuration, environment, implementation version, and (if later applicable) random seed, the
ordered state sequence must be reproducible. Tests should compare sequences at tick boundaries, not
wall-clock arrival times.

Early phases add no random noise. Later noise or randomized faults must receive an explicit seeded
random source owned by run configuration; the seed must be recorded and tests must use fixed seeds.
Thread scheduling, unordered iteration, and wall-clock timing must not influence numerical results.

## Canonical units and numerical policy

| Quantity | Canonical representation / unit |
| --- | --- |
| Simulation timestamp and fixed-step duration | unsigned 64-bit integer microseconds |
| Human-scale duration / equation delta | seconds, derived explicitly from integer time |
| Engine speed | revolutions per minute (rpm) |
| Vehicle speed | meters per second (m/s) |
| Temperature | degrees Celsius (°C) |
| Physical pressure | kilopascals absolute (kPa abs) |
| Boost relative to ambient | kilopascals gauge (kPa gauge), named explicitly |
| Angle | degrees |
| Pedal, throttle, and normalized load | dimensionless `[0, 1]` |
| Lambda | dimensionless equivalence ratio |
| Voltage | volts (V) |
| Torque | newton-metres (N·m) |
| Power | kilowatts (kW) |
| Mass | kilograms (kg) |
| Distance | metres (m) |

Fuel units are deferred until a concrete Phase 1+ field needs them. Continuous physical quantities
use finite `double` values; discrete modes use enums or explicit integer codes. Field names include
units where practical. TunerOS adds no custom units library and permits no scattered magic
conversion constants. Counts and time use unsigned integers because negative values are invalid;
gear uses a signed integer so `-1` can represent reverse.

Internal engineering state stays canonical. Inputs, configuration loaders, CAN encoding/decoding,
APIs, and UI presentation are explicit conversion boundaries. A UI may display mph, psi, horsepower,
or °F without changing simulation state.

## Pressure semantics

- **Ambient pressure:** environment pressure surrounding the vehicle, kPa absolute.
- **Manifold absolute pressure (MAP):** intake-manifold physical pressure, kPa absolute.
- **Boost gauge pressure:** pressure relative to current ambient, kPa gauge. It may be negative under
  manifold vacuum.
- **Requested boost:** a controller target relative to ambient, kPa gauge in the initial contract.
- **Actual boost:** a derived observation, not independently owned state:
  `actual_boost_kpa_gauge = manifold_pressure_kpa_absolute - ambient_pressure_kpa_absolute`.

Code and documentation must retain the `absolute` or `gauge` qualifier where ambiguity is possible.
Sea-level pressure is never a universal constant. The run environment supplies ambient pressure.

## VehicleState ownership

`VehicleState` is the authoritative internal physical/logical state before ECU observation and CAN
publication. It contains no UI formatting and no encoded signals. Phase 1 tests and local simulator
tools may inspect it directly while CAN does not exist; that temporary development access is not a
production telemetry path.

| Canonical field | Meaning | Unit / invariant | Owner/source | Phase 1 |
| --- | --- | --- | --- | --- |
| `timestamp` | time since run reset | integer µs, monotonic | simulation clock | Required |
| `run_state` | stopped, running, paused, or completed | enum | simulation clock/runner | Required |
| `accelerator_pedal_position` | scenario driver demand | `[0,1]` | scenario input | Required |
| `requested_scenario_load` | optional generalized load stimulus | `[0,1]` | scenario input | Reserved |
| `engine_running` | whether combustion-driven operation is active | boolean | vehicle model | Required |
| `engine_speed_rpm` | crankshaft rotational speed | rpm, `[0, profile redline]` initially | vehicle model | Required |
| `engine_load` | simplified normalized engine load | `[0,1]` | vehicle model | Required |
| `throttle_position` | simplified effective throttle opening | `[0,1]` | vehicle model/controller result | Required |
| `vehicle_speed_meters_per_second` | longitudinal speed magnitude | m/s, non-negative initially | vehicle model | Required |
| `current_gear` | selected gear | `-1` reverse, `0` neutral, `1..gear_count` forward | transmission/vehicle model | Required |
| `ambient_pressure_kpa_absolute` | run ambient pressure snapshot | kPa abs, non-negative | environment input | Required |
| `manifold_pressure_kpa_absolute` | intake manifold pressure | kPa abs, non-negative | vehicle model | Reserved |
| `requested_boost_kpa_gauge` | simplified boost target above ambient | kPa gauge, finite | future DME controller | Reserved |
| `actual_boost_kpa_gauge()` | derived MAP relative to ambient | kPa gauge, finite | derived VehicleState observation | Reserved |
| `coolant_temperature_celsius` | representative coolant temperature | °C, finite | vehicle thermal state | Required |
| `oil_temperature_celsius` | representative engine-oil temperature | °C, finite | vehicle thermal state | Required |
| `intake_air_temperature_celsius` | representative intake charge temperature | °C, finite | vehicle/environment model | Required |
| `lambda` | actual mixture equivalence ratio | dimensionless, `> 0` | combustion/fueling state | Reserved |
| `ignition_advance_degrees` | aggregate spark angle relative to TDC | degrees, finite; positive is advance | future DME/controller result | Reserved |
| `timing_correction_degrees` | aggregate commanded ignition retard | degrees, finite and `<= 0` | future DME/controller result | Reserved |
| `battery_voltage_volts` | electrical-system voltage | V, non-negative | vehicle electrical state | Required |

The initial validator checks profile validity, finite continuous values, normalized ranges,
non-negative rpm/speed/absolute pressures/voltage, valid gear range, positive lambda, non-positive
timing correction, and the profile redline. It validates snapshots at construction/loading/test
boundaries; it does not replace component-specific transition invariants.

State ownership remains one-way:

```text
Scenario + Environment + VehicleProfile
                  -> Vehicle simulation owns VehicleState
                  -> ECUs observe state and own controller/internal ECU state
                  -> ECUs publish selected values as binary CAN signals
                  -> DBC decoding creates named engineering signals
                  -> telemetry owns decoded observations and application history
```

ECU state includes controller memory, targets, and counters that are not physical vehicle state. CAN
signals are selected, scaled publications rather than a memory view. Telemetry state is downstream
decoded/current/historical data. The backend must never take privileged `VehicleState` access to
bypass ECU → CAN → DBC, even if doing so is convenient.

## Scenario contract

A `Scenario` is deterministic, time-indexed input data. Its definition contains an identifier,
simulation duration, initial conditions, driver inputs over simulation time, environment inputs, and
optional descriptive metadata. Planned identifiers are `IDLE`, `COLD_START`, `WARMUP`, `CITY`,
`HIGHWAY`, `SPIRITED`, `WOT_PULL`, and `DYNO_PULL`; only IDLE is implemented in Phase 1A.

A scenario provides stimuli. It does **not** set resulting rpm every tick, generate CAN frames,
create diagnostic faults, implement controllers, or manipulate frontend state. The vehicle model
determines outcomes from scenario inputs and configuration. Faults will later be separate run
configuration, not hidden scenario side effects.

### Implemented Phase 1A IDLE behavior

IDLE is a category B realistic simplification, not an implementation of BMW idle control:

- start at simulation time zero with engine running, neutral gear, zero vehicle speed, accelerator
  input `0.0`, no requested boost, and no faults;
- use the run's ambient temperature and pressure; the default local environment is 20 °C and
  101.325 kPa absolute (category C modeling defaults);
- use a default duration of 60 seconds (category C) but allow tests to choose another positive
  simulation duration;
- use the 10 ms base step and do not pace tests against wall time;
- initialize engine speed at 850 rpm and keep it in the broad 650–900 rpm acceptance band while it
  approaches the 750 rpm TunerOS target;
- keep `vehicle_speed_meters_per_second == 0`, `current_gear == 0`, and
  `accelerator_pedal_position == 0` at every tick;
- keep all snapshots valid; coolant and oil temperature must be non-decreasing during this normal
  warmup case and remain finite, without prescribing a thermal equation;
- engine-running battery voltage must stay in the category B range 13.0–15.0 V;
- produce no faults and no CAN output because neither subsystem exists in Phase 1.

Other scenario identifiers remain reserved. Constructing a Phase 1A simulation for any of them
throws `std::invalid_argument` rather than substituting IDLE behavior.

## Phase 1A numerical model and parameters

All dynamic quantities use the same exact first-order update, evaluated once per configured step:

```text
next = target + (current - target) * exp(-delta_time_seconds / time_constant_seconds)
delta_time_seconds = fixed_step_microseconds / 1,000,000
```

The integer timestamp remains authoritative; no floating-point time is accumulated. The exponential
form is stable for positive steps and makes equivalent elapsed durations tightly consistent across
reasonable step sizes.

All values below are category B/C TunerOS modeling assumptions, not BMW calibrations:

| Quantity | Initial / fixed value | Target | Time constant |
| --- | ---: | ---: | ---: |
| Engine speed | 850 rpm | 750 rpm | 1.5 s |
| Coolant temperature | ambient + 5 °C | 92 °C | 300 s |
| Oil temperature | ambient + 2 °C | 100 °C | 600 s |
| Intake-air temperature | ambient + 3 °C | ambient + 10 °C | 60 s |
| Battery voltage | 13.8 V | 14.2 V | 1.0 s |

Fixed Phase 1A baselines are accelerator `0.0`, requested scenario load `0.10`, engine load `0.18`,
throttle position `0.06`, vehicle speed `0 m/s`, neutral gear, requested boost `0 kPa gauge`, lambda
`1.0`, ignition advance `8 degrees`, and timing correction `0 degrees`. Manifold absolute pressure is
`0.40 * ambient_pressure_kpa_absolute`, preserving manifold vacuum across configured environments.

Phase 1A dynamically models RPM, coolant, oil, intake-air temperature, and battery voltage. Scenario
inputs and environment snapshots are applied each tick. Stationary/neutral state, load, throttle,
pressure ratio, lambda, and ignition values are fixed deterministic baselines. Requested boost and
timing correction are reserved fixed-zero placeholders for later controller phases.

`SimulationRunConfiguration` contains only vehicle profile, scenario, duration, fixed step, and
environment. Its default IDLE run is 60 seconds at 10 ms. Duration and step must be positive, and
duration must contain an integer number of fixed steps so completion has an exact timestamp.

## Environment and configuration boundaries

`EnvironmentState` initially contains only ambient temperature in °C and ambient pressure in kPa
absolute. Run configuration may override both. Humidity, weather, and external APIs are excluded
until a concrete requirement exists.

Configuration remains separated by lifecycle and owner:

| Category | Examples | Owner / lifecycle |
| --- | --- | --- |
| Build/developer | database connection, service ports | deployment/tooling; outside simulation state |
| Vehicle profile | E90/N54 static identity, displacement, limits | selected before a run; immutable during it |
| Simulation run | scenario, duration, fixed step, environment, future seed | per run |
| Calibration | future boost targets, ignition maps, lambda targets | controller configuration; not implemented |
| Fault | future boost leak or sensor failure injection | explicit per run; not implemented |

These categories must not collapse into one global configuration object.

## Terminology

- **DME:** BMW term for the digital motor electronics / engine control module.
- **ECU:** generic electronic control unit; use it for architectural roles spanning manufacturers.
- **CAN:** Controller Area Network; the future binary telemetry boundary.
- **DBC:** database description format used to map CAN payload bits to engineering signals.
- **VehicleState:** authoritative pre-ECU physical/logical simulation snapshot.
- **VehicleProfile:** relatively static BMW-focused vehicle configuration.
- **Scenario:** deterministic time-indexed stimuli and initial/environment conditions.
- **SimulationClock:** fixed-step owner of simulation timestamp and tick progression.
- **Telemetry:** decoded observations downstream of CAN/DBC, live or persisted.
- **DTC:** diagnostic trouble code with a defined lifecycle.
- **Freeze Frame:** snapshot captured when a qualifying diagnostic event occurs.
- **Calibration:** future controller targets/maps/parameters, separate from vehicle identity.
- **DSC:** BMW terminology for Dynamic Stability Control.
- **EGS:** BMW transmission-control terminology, applicable when that controller is modeled.
