# Simulation contracts

This specification defines the stable engineering contracts and records the Phase 1A–1C
deterministic simulation implementation. Only vehicle-side clock,
initial/environment configuration,
scenario input, orchestration, and minimal state evolution exist. Phase 2A consumes this state
through a read-only simulated DME and synthetic CAN boundary; application layers remain
unimplemented.

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
gear uses a signed integer for the neutral/forward domain; reverse remains unimplemented.

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
publication. It contains no UI formatting and no encoded signals. Tests and simulator-only tools may
inspect it directly; production telemetry must use ECU publication and the CAN/decode path.

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
| `current_gear` | selected gear | `0` neutral, `1..gear_count` forward | transmission/vehicle model | Required |
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
Scenario + Environment + InitialConditions + VehicleProfile
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

A `Scenario` is deterministic, time-indexed input data. `scenario_inputs_for()` is a stateless
function of scenario identifier, integer simulation timestamp, and environment. It returns only
accelerator, requested load, stationary command, engine-start request, and environment snapshot.
Scenario phases are therefore fully time-derived and need no resettable hidden state.

Planned identifiers are `IDLE`, `COLD_START`, `WARMUP`, `CITY`, `HIGHWAY`, `SPIRITED`, `WOT_PULL`,
and `DYNO_PULL`. IDLE, COLD_START, WARMUP, and CITY are implemented through Phase 1C.

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

HIGHWAY, SPIRITED, WOT_PULL, and DYNO_PULL remain reserved. Constructing a Phase 1C simulation
for any of them throws `std::invalid_argument` rather than substituting implemented behavior.

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

`SimulationRunConfiguration` contains only vehicle profile, scenario, duration, fixed step,
environment, and focused initial conditions. Its default IDLE run is 60 seconds at 10 ms. Duration
and step must be positive, and duration must contain an integer number of fixed steps so completion
has an exact timestamp.

## Phase 1B initial-condition contract

`SimulationInitialConditions` contains engine-running state, engine RPM, coolant/oil/intake-air
temperatures, battery voltage, vehicle speed, and gear. It does not mirror scenario inputs,
environment pressure, model targets, derived pressure, lambda, ignition, or run state.

Validation requires finite/non-negative RPM, speed, and voltage; finite temperatures; RPM within the
profile limit; and gear within the neutral/forward profile range. A stopped engine must have exactly
zero RPM. Implemented runs begin at zero speed and neutral gear. IDLE, WARMUP, and CITY require an
initially running engine; COLD_START requires an initially stopped engine.

Default factories take an explicit `EnvironmentState` and build matching initial conditions. A
caller may then replace any focused initial field before constructing `VehicleSimulation`.

## Phase 1B COLD_START schedule

All values are TunerOS modeling assumptions, not BMW specifications or calibration:

- default duration: 90 seconds;
- before 1,000,000 µs: engine-start request false, requested load `0.0`, engine exactly off at
  `0 rpm`, battery target 12.6 V, and manifold pressure equal to ambient;
- at exactly 1,000,000 µs: engine-start request becomes true and requested load becomes `0.40`;
- from 1,000,000 through 21,000,000 µs: requested load decreases linearly from `0.40` to normal
  idle `0.10`;
- the vehicle model maps that request to an RPM target from 1,200 to 750 rpm, engine load from `0.48`
  to `0.18`, and throttle from `0.10` to `0.06`;
- RPM uses a 0.75 s time constant while elevated load remains, then the normal 1.5 s idle constant;
- after engine start, voltage approaches 14.2 V and thermal state uses the existing bounded model.

Cold-start coolant, oil, and intake air default to ambient temperature. No crank-voltage dip,
starter physics, fuel enrichment, crank-angle behavior, misfire, or noise is modeled.

## Phase 1B WARMUP behavior

WARMUP defaults to 300 simulated seconds, engine-running at 750 rpm, with coolant at ambient + 20 °C,
oil at ambient + 15 °C, intake air at ambient + 5 °C, and battery voltage at 14.2 V. It supplies the
same zero-accelerator/normal-idle inputs as IDLE. Its purpose is configurable warmer initial state and
long bounded thermal progression; it has no invented extra control behavior.

## Phase 1C CITY input schedule

CITY is a 105-second TunerOS synthetic drive schedule. Its scenario function remains stateless and
selects inputs solely from the integer simulation timestamp. Interval starts are inclusive:

| Simulation interval | Accelerator | Requested load | Stationary intent |
| --- | ---: | ---: | --- |
| `[0, 5)` s | 0.00 | 0.10 | true |
| `[5, 20)` s | 0.45 | 0.50 | false |
| `[20, 32)` s | 0.30 | 0.35 | false |
| `[32, 45)` s | 0.00 | 0.10 | false |
| `[45, 55)` s | 0.00 | 0.10 | true |
| `[55, 75)` s | 0.55 | 0.60 | false |
| `[75, 88)` s | 0.36 | 0.40 | false |
| `[88, 100)` s | 0.00 | 0.10 | false |
| `[100, 105]` s | 0.00 | 0.10 | true |

The scenario never assigns final speed, gear, RPM, engine load, throttle, or pressure. A stationary
input is an intent consumed by the vehicle response, not an instantaneous speed command. There is no
hidden scenario phase state, event bus, script, route, or random driver variation.

The default CITY initial conditions are engine-running at 750 rpm, zero speed, neutral gear,
14.2 V, coolant at ambient + 35 degrees Celsius, oil at ambient + 30 degrees Celsius, and intake air
at ambient + 5 degrees Celsius.

## Phase 1C longitudinal and drivetrain response

All parameters in this section are category B/C TunerOS assumptions, not BMW calibration or a full
vehicle-physics model. For non-stationary input, one tick computes:

```text
drive_acceleration = accelerator * 2.0 m/s^2
resistance = speed > 0 ? 0.45 m/s^2 + 0.025 / s * speed : 0
acceleration = drive_acceleration - resistance
next_speed = max(0, speed + acceleration * delta_time_seconds)
```

Stationary intent instead applies `-1.5 m/s^2` until speed reaches zero; a value at or below the
0.05 m/s stop epsilon is clamped exactly to zero. This supports repeatable stops without introducing
mass, torque, power, tire, clutch, brake, road-grade, or energy-balance models.

CITY uses a synthetic scenario-controlled manual-driver gear schedule in the vehicle response:

| Speed | Selected gear |
| --- | ---: |
| stationary intent and speed <= 0.05 m/s | 0 |
| below 4.5 m/s | 1 |
| 4.5 to below 8.0 m/s | 2 |
| 8.0 to below 12.0 m/s | 3 |
| 12.0 m/s or above | 4 |

This schedule is not automatic-transmission behavior, an EGS, or a clutch model. Gears 5 and 6 are
valid profile gears and have coupling factors for focused drivetrain tests, but the default CITY
schedule does not reach them. Engine speed is recomputed from the selected gear and speed:

```text
engine_rpm = clamp(speed * rpm_per_meter_per_second[gear], 750 rpm, profile_redline)
```

The synthetic factors for gears 1 through 6 are respectively `310`, `200`, `145`, `110`, `90`, and
`75 rpm per m/s`. Neutral or zero-speed engine-running behavior returns the 750 rpm idle floor.
An upshift can therefore create a deterministic RPM drop without clutch-slip dynamics.

CITY maps requested load to normalized engine load as
`clamp(0.08 + requested_load, 0, 1)` and accelerator to throttle as
`clamp(0.06 + 0.60 * accelerator, 0, 1)`. Its MAP ratio is:

```text
load_above_idle = clamp((requested_load - 0.10) / 0.90, 0, 1)
map_ratio = 0.40 + (1.00 - 0.40) * load_above_idle
manifold_absolute_pressure = ambient_absolute_pressure * map_ratio
```

Thus higher CITY load reduces manifold vacuum while MAP remains at or below ambient. Requested boost
remains zero. No turbo or boost-control dynamics are implied. Existing thermal, intake-air, and
charging-voltage first-order responses continue during motion.

CITY does not require schedule boundaries to align with the fixed step. Inputs are evaluated at each
exact post-advance integer timestamp, so a 15 ms step crosses the 5-second boundary at 5.010 seconds
without rounding, floating-point time accumulation, or hidden phase state. Identical configurations
produce identical sequences; 10 ms, 20 ms, and boundary-misaligned 15 ms runs are compared for
physically consistent outcomes rather than bit equality across different step sizes.

## Reset and state evolution

Each tick advances the integer clock first, evaluates stateless inputs for that resulting timestamp,
then evolves `VehicleState` across that fixed step. This makes the cold-start transition observable at
exactly 1,000,000 µs for both 10 ms and 20 ms steps. COLD_START configuration requires its 1-second
request boundary and 20-second stabilization duration to be integer multiples of the selected step.

Reset sets clock timestamp/tick count to zero, clears pause state, and copies the exact initial
`VehicleState` captured from the immutable run configuration. Because scenario schedules are
stateless, no scenario phase state exists to reset. Repeating a run after reset produces the same
state sequence.

Through Phase 1C, the model dynamically owns engine-running transition, RPM, engine load, throttle,
manifold pressure, speed, forward gear selection, coolant/oil/intake-air temperatures, and battery
voltage where scenario inputs require them. Speed and gear remain stationary/neutral in IDLE,
COLD_START, and WARMUP and evolve only in CITY. Requested boost, lambda, ignition baseline, and timing
correction remain deterministic placeholders.

## Environment and configuration boundaries

`EnvironmentState` initially contains only ambient temperature in °C and ambient pressure in kPa
absolute. Run configuration may override both. Humidity, weather, and external APIs are excluded
until a concrete requirement exists.

Configuration remains separated by lifecycle and owner:

| Category | Examples | Owner / lifecycle |
| --- | --- | --- |
| Build/developer | database connection, service ports | deployment/tooling; outside simulation state |
| Vehicle profile | E90/N54 static identity, displacement, limits | selected before a run; immutable during it |
| Simulation run | scenario, duration, fixed step, environment, initial conditions, fault configuration | per run |
| Calibration | future boost targets, ignition maps, lambda targets | controller configuration; not implemented |
| Fault | four Phase 7B physical/system or sensor effects | explicit, immutable per run |

These categories must not collapse into one global configuration object.

## Terminology

- **DME:** BMW term for the digital motor electronics / engine control module.
- **ECU:** generic electronic control unit; use it for architectural roles spanning manufacturers.
- **CAN:** Controller Area Network; the future binary telemetry boundary.
- **DBC:** database description format used to map CAN payload bits to engineering signals.
- **VehicleState:** authoritative pre-ECU physical/logical simulation snapshot.
- **VehicleProfile:** relatively static BMW-focused vehicle configuration.
- **SimulationInitialConditions:** focused configurable starting engine, thermal, electrical, speed,
  and gear values used to construct the initial `VehicleState`.
- **Scenario:** deterministic time-indexed stimuli selected by scenario identifier.
- **ScenarioInputs:** stateless, time-derived driver/environment/control requests consumed by the
  vehicle model; never final physical outputs.
- **FaultConfiguration:** stable fault ID plus simulation-time activation and optional deactivation;
  orthogonal to the scenario and retained across reset.
- **SensorObservation:** transient ECU-facing view that can differ from canonical physical truth
  only for an active sensor fault.
- **SimulationClock:** fixed-step owner of simulation timestamp and tick progression.
- **Telemetry:** decoded observations downstream of CAN/DBC, live or persisted.
- **DTC:** diagnostic trouble code with a defined lifecycle.
- **Freeze Frame:** snapshot captured when a qualifying diagnostic event occurs.
- **Calibration:** future controller targets/maps/parameters, separate from vehicle identity.
- **DSC:** BMW terminology for Dynamic Stability Control.
- **EGS:** BMW transmission-control terminology, applicable when that controller is modeled.
