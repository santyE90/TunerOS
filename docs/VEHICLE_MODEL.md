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
  dynamics despite `-1` being reserved as the reverse gear representation.
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
