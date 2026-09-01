# Vehicle model specification

## Scope and modeling philosophy

TunerOS models one coherent BMW-oriented reference configuration before broadening its scope. It is
an educational and portfolio system, not an OEM-perfect digital twin, production controller, or
reproduction of proprietary BMW software. Believable, internally consistent, observable behavior is
more valuable here than high-fidelity physics. Complexity must earn its place by making an
engineering boundary or relationship clearer.

The reference configuration is a **2010 BMW E90 335i sedan with an N54B30 gasoline engine and a
six-speed manual transmission**. It is the configuration TunerOS elects to model; it is not a claim
that every 2010 335i in every market had this engine, body, drivetrain, or transmission. Model-year,
market, production-date, and body-style differences matter in the real product line.

## Authenticity classification

Every automotive claim, value, identifier, threshold, mapping, or algorithm should use one of these
labels when its provenance may otherwise be unclear:

- **A — Public / real-world reference:** publicly known and reasonably verifiable. Examples: the N54
  is an inline six using two exhaust-driven turbochargers; the reference engine displacement is
  2,979 cm³.
- **B — TunerOS realistic simplification:** inspired by real vehicle behavior but deliberately less
  detailed. Examples: a future first-order turbo spool equation or a single aggregate timing
  correction instead of cylinder-level control behavior.
- **C — TunerOS synthetic:** invented by this project. Examples: a TunerOS calibration ID, a chosen
  diagnostic threshold, or a future CAN arbitration ID such as `0x123` unless separately sourced.

Use the classification where it adds clarity, not as paperwork on every sentence. Plausible is not
the same as authentic. Simplifications must be called simplifications, and synthetic TunerOS data
must never be represented as BMW data.

## Reference characteristics

The deliberately small set of category A facts used by the initial profile is:

| Characteristic | Reference value | Classification and source |
| --- | --- | --- |
| Manufacturer / platform / model | BMW E90 335i sedan | A — public model designation; this exact TunerOS configuration is scoped above |
| Engine | N54B30, gasoline inline six | A — BMW's [N54 training material](https://bmwtechinfo.bmwgroup.com/tech_training_manual/ST501%20Engine%20Technology.pdf) describes the N54 as a 3.0 L member of its six-cylinder engine family |
| Cylinder count | 6 | A — same BMW training material |
| Displacement | 2,979 cm³ (2.979 L) | A — BMW's [2010 335i technical specifications](https://www.press.bmwgroup.com/canada/article/attachment/T0037174EN/105889) |
| Induction | Two exhaust-driven turbochargers with charge-air cooling | A — BMW N54 training material |
| Fuel system concept | Gasoline direct injection | A — BMW N54 training material; no injector or control algorithm is modeled here |
| Published upper operating point | approximately 7,000 rpm | A — BMW's period [335i description](https://www.press.bmwgroup.com/united-kingdom/article/detail/T0018958EN_GB/the-new-bmw-3-series-coup%C3%A9) reports a 7,000 rpm maximum; TunerOS uses it as the profile redline, not a claim about limiter behavior |

No proprietary maps, tables, CAN data, or exact DME algorithms are inferred from these facts.

## Initial VehicleProfile

`VehicleProfile` is relatively static vehicle configuration. Phase 1A implements
`make_e90_335i_n54_manual_profile()` as the single concrete factory for this profile. It returns the
documented values below and passes the existing contract validator; no external loader or
calibration data is introduced.

| Field | Initial E90/N54 profile | Classification |
| --- | --- | --- |
| `profile_id` | `bmw-e90-335i-n54-2010-manual` | C — TunerOS synthetic identifier |
| `manufacturer` | BMW | A |
| `model` | 335i | A |
| `chassis` | E90 | A |
| `model_year` | 2010 | A for the selected reference |
| `engine_family` | N54 | A |
| `engine_identifier` | N54B30 | A |
| `cylinder_count` | 6 | A |
| `displacement_liters` | 2.979 | A |
| `fuel_type` | gasoline | A |
| `induction_type` | twin turbo | A |
| `transmission_type` | manual | B — TunerOS selection from a real available configuration |
| `forward_gear_count` | 6 | B — TunerOS reference-profile selection |
| `redline_rpm` | 7,000 | A reference used as a modeling limit; no limiter algorithm implied |
| `baseline_calibration_id` | `tuneros-n54-stock-baseline-v0` | C — namespace only; no calibration exists in Phase 0B |

Profile validation rejects missing identifiers, zero cylinders, non-positive/non-finite displacement,
zero gears, and non-positive/non-finite redline. Validation occurs through explicit, non-throwing
helpers at loading and test boundaries. Aggregate structs remain easy to inspect; constructors do not
hide normalization or mutate data.

The profile is intentionally BMW-first rather than a universal vehicle schema. M52, M54, N52, N55,
and further N54 variants may later reuse or carefully extend it, but Phase 0B defines no additional
profiles.

## Initial modeling assumptions

These are not verified BMW calibration values:

- **B — TunerOS realistic simplification:** vehicle motion is initially non-negative, with no reverse
  dynamics. Phase 1C validates only neutral (`0`) and forward gears (`1..6`); reverse remains
  unimplemented.
- **B — TunerOS realistic simplification:** one normalized engine-load value and one aggregate,
  non-positive timing-correction value stand in for much richer controller and cylinder-level data.
- **C — TunerOS synthetic:** normalized positions use `[0, 1]`; profile and calibration identifiers
  belong to TunerOS.
- **C — TunerOS synthetic modeling defaults:** local ambient conditions begin at 20 °C and
  101.325 kPa absolute unless a run overrides them. These are convenient defaults, not universal
  atmosphere.
- **B — TunerOS realistic simplification:** the initial IDLE acceptance band and thermal monotonicity
  rules are defined in [Simulation contracts](SIMULATION_CONTRACTS.md), not taken from BMW control
  software.

## Phase 1A implemented IDLE model

Phase 1A implements one category B deterministic simplification. The IDLE scenario supplies zero
accelerator, normalized requested load `0.10`, a stationary command, and stable environment input.
It does not assign resulting RPM or temperatures. `VehicleSimulation` applies those inputs to the
vehicle response.

The initial/default assumptions are 850 rpm, coolant at ambient + 5 °C, oil at ambient + 2 °C,
intake air at ambient + 3 °C, and battery voltage at 13.8 V. RPM approaches 750 rpm; coolant
approaches 92 °C; oil approaches 100 °C; intake air approaches ambient + 10 °C; and voltage
approaches 14.2 V. The exact time constants and remaining fixed baselines are recorded in
[Simulation contracts](SIMULATION_CONTRACTS.md). These values and equations are TunerOS modeling
assumptions, not BMW calibration or DME behavior.

Vehicle speed stays 0 m/s and gear stays neutral. No drivetrain, torque, turbo, fueling, ignition
control, ECU, CAN, diagnostic, or calibration model exists.

## Phase 1B initial conditions and scenarios

`SimulationInitialConditions` configures only starting values that materially affect the current
model: engine-running state, engine RPM, coolant/oil/intake-air temperatures, battery voltage,
vehicle speed, and gear. It deliberately does not duplicate `VehicleState`.

Initial-state ownership is:

- `VehicleProfile`: redline and valid gear range;
- `EnvironmentState`: ambient temperature and absolute pressure;
- `SimulationInitialConditions`: the eight configurable starting values above;
- scenario inputs: accelerator, requested load, stationary command, and engine-start request;
- vehicle-model defaults: load/throttle relationships, manifold-pressure ratio, lambda, ignition
  baseline, requested boost, timing correction, targets, and time constants.

The Phase 1B stationary scenarios require neutral initial gear and zero speed. IDLE retains its
Phase 1A initial state and observable numerical behavior.

### COLD_START

COLD_START is a TunerOS realistic simplification, not BMW/N54 startup strategy. It starts engine-off
at zero RPM, with coolant/oil/intake air equal to configured ambient temperature, manifold pressure
equal to ambient, and battery voltage at 12.6 V. At exactly 1.0 second of simulation time, the
scenario requests engine start and an elevated normalized load of `0.40`. The vehicle model owns the
transition to `engine_running`, charging voltage, manifold vacuum, and rising RPM.

Elevated requested load decays linearly to the normal `0.10` idle request over 20 seconds. The
vehicle model maps that input to a target that falls from 1,200 to 750 rpm and applies deterministic
first-order response. No starter, enrichment, misfire, crank-angle, or alternator physics is modeled.
The default run duration is 90 seconds.

### WARMUP

WARMUP begins engine-running at 750 rpm, stationary and neutral. Default coolant, oil, and intake-air
temperatures are ambient + 20 °C, ambient + 15 °C, and ambient + 5 °C respectively; callers may
replace them through `SimulationInitialConditions`. It uses normal idle inputs and the existing
bounded thermal response for a default five-minute simulated run. It adds no artificial behavior
solely to distinguish it from IDLE.

## Phase 1C CITY scenario and drivetrain simplification

CITY adds the first moving-vehicle behavior without claiming a physical drivetrain model. The
scenario remains a stateless, integer-time input schedule. It supplies accelerator, requested load,
and stationary intent; it never assigns speed, gear, RPM, or manifold pressure. The vehicle model
owns those resulting values.

The default CITY initial state is engine-running at 750 rpm, stationary and neutral, with coolant at
ambient + 35 degrees Celsius, oil at ambient + 30 degrees Celsius, intake air at ambient + 5 degrees
Celsius, and battery voltage at 14.2 V. These offsets and every value below are TunerOS modeling
assumptions.

Longitudinal response is intentionally synthetic: accelerator demand provides up to 2.0 m/s^2,
rolling resistance is 0.45 m/s^2 while moving, linear speed resistance is
`0.025 * speed` m/s^2, and stationary intent applies 1.5 m/s^2 of deceleration. Integration uses the
configured fixed-step duration. This is not a force balance and introduces no mass, torque, tire,
clutch, or road-grade model.

CITY uses a deterministic hypothetical manual-driver schedule: first gear below 4.5 m/s, second
below 8.0 m/s, third below 12.0 m/s, and fourth at higher CITY speeds. Neutral is selected only when
stationary intent has brought speed to zero. This is neither automatic-transmission logic nor an
EGS or clutch model. Engine speed is directly coupled to vehicle speed by the following synthetic
factors and clamped to the 750 rpm idle floor and profile redline:

| Gear | RPM per m/s |
| ---: | ---: |
| 1 | 310 |
| 2 | 200 |
| 3 | 145 |
| 4 | 110 |
| 5 | 90 |
| 6 | 75 |

The 105-second default schedule contains an initial 5-second idle, acceleration to 20 seconds,
cruise demand to 32 seconds, coast/deceleration to 45 seconds, a stop through 55 seconds, a second
acceleration to 75 seconds, cruise demand to 88 seconds, deceleration to 100 seconds, and a final
stop. Exact input values and interval boundaries are recorded in
[Simulation contracts](SIMULATION_CONTRACTS.md).

CITY remains naturally aspirated in the simplified pressure response: requested boost is zero and
MAP moves from the 0.40 ambient-pressure idle ratio toward, but never above, ambient as requested
load rises. This is an illustrative vacuum/load relationship, not an N54 turbo or throttle model.

HIGHWAY, SPIRITED, WOT_PULL, and DYNO_PULL remain unsupported. Phase 1C adds no reverse motion,
engine stopping, torque production, road load, turbo dynamics, clutch behavior, wheel dynamics, or
traction behavior.
