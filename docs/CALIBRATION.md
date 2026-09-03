# Calibration and tuning foundation

## Scope and authority

Phase 8B adds a **simulation-only** calibration domain for the synthetic 2010 BMW E90 335i / N54
reference model. Every value here is a TunerOS modeling assumption: it is not BMW factory data,
reverse-engineered OEM calibration, or suitable for ECU flashing or real-vehicle tuning.

```text
immutable C++ CalibrationProfile -> powertrain response -> VehicleState -> simulated ECU
  -> raw CAN -> authoritative DBC -> Python telemetry/session/investigation -> frontend
```

The C++ profile is authoritative for behavior. Python has a read-only copy of public metadata for
inspection, no calibration physics or runtime mutation. The frontend never synthesizes telemetry.

## Profiles and revisioning

Exactly two profiles exist. `stock` revision 1 is the default and preserves prior non-WOT behavior.
`stage-1` revision 1 is a synthetic higher-output comparison. Selection is immutable for a run.

| Parameter | Stock r1 | Stage 1 r1 | Unit |
| --- | ---: | ---: | --- |
| boost response time constant | 0.80 | 0.65 | s |
| engine output multiplier | 1.00 | 1.08 | ratio |

## Typed maps

`Axis1D` requires a name/unit and at least two finite, strictly increasing breakpoints. `Table1D`
requires one finite value per breakpoint. `Table2D` requires finite row-major values matching rows
times columns. Coordinates clamp to the closest edge. Interiors use linear or bilinear interpolation.

Throttle response, pedal axis `[0, .25, .5, .75, 1]`:

| Profile | Values (normalized load) |
| --- | --- |
| Stock | `[0, .22, .48, .74, 1]` |
| Stage 1 | `[0, .28, .60, .86, 1]` |

Boost target uses RPM rows `[1000, 2500, 4000, 5500, 6500]`, load columns `[0, .5, 1]`, kPa gauge:

| Profile | Row-major values |
| --- | --- |
| Stock | `[0,0,0; 0,25,70; 0,35,90; 0,28,75; 0,10,40]` |
| Stage 1 | `[0,0,0; 0,35,95; 0,50,125; 0,45,110; 0,20,65]` |

Lambda target uses load axis `[0, .5, .8, 1]`: Stock `[1, 1, .90, .86]`; Stage 1
`[1, 1, .88, .82]`.

Ignition target uses RPM rows `[2000, 3500, 5000, 6500]`, load columns `[0, .5, 1]`, degrees:

| Profile | Row-major values |
| --- | --- |
| Stock | `[18,14,10; 22,15,8; 24,16,7; 20,12,5]` |
| Stage 1 | `[18,14,9; 22,16,10; 24,18,9; 20,14,7]` |

## WOT_PULL model

This standardized synthetic pull starts at 15 m/s in fixed third gear, runs exactly 12,000,000
simulation microseconds, uses pedal/load `.12/.18` until 2,000,000 microseconds, then `1/1`. RPM is
speed times the existing third-gear factor, clamped to idle/redline. It never shifts.

For fixed step `dt`, calibrated demand comes from the throttle table. Boost target comes from the 2D
map and actual boost uses `x += (target-x) * (1-exp(-dt/tau))`. MAP is ambient absolute pressure plus
actual gauge boost. Lambda and ignition use the same form with 0.25 s and 0.20 s time constants.
Intake-air equilibrium adds `0.08 °C` per positive kPa gauge to the existing equilibrium.

Normalized output is
`demand * output_multiplier * (1 + .35 * positive_boost / max(1, ambient_kPa))`.
Acceleration is `clamp(output,0,2) * 3.0 - (0.45 + .025 * speed)` in m/s². This is a response signal
model, not torque or horsepower. Existing IDLE/CITY equations remain isolated and unchanged.

## CAN observation

Existing CAN IDs, DLCs, layouts, and non-WOT schedules are unchanged. WOT_PULL enables synthetic DME
frame `0x503` (`DmeCombustionObservation`), DLC 3, every 20,000 µs. The DBC defines `Lambda` as an
unsigned byte with scale 0.01 and `IgnitionTiming` as little-endian unsigned 16-bit with scale 0.1,
offset -100 degrees. Encoding saturates safely. Calibration ID is not encoded on CAN.

## Selection, provenance, and analysis

The gateway accepts `--calibration stock|stage-1`; omission means Stock and unknown values fail.
Profiles cannot change mid-run. The backend catalog provides read-only `GET /api/v1/calibrations`
and `GET /api/v1/calibrations/{profile_id}`; `/calibration` renders metadata, units, maps, and deltas.

Legacy session v1 remains raw CAN plus original metadata and displays **Unknown / Legacy**. Session
v2 adds `calibration_id` and `calibration_revision` while retaining raw CAN as canonical evidence.
Both replay without the C++ model. Calibration is provenance, not diagnostic input and not a
comparison compatibility condition; matching vehicle/network sessions may compare across profiles.

Authentic BMW maps, physical CAN, flashing, runtime editing, BIN/XDF, horsepower/dyno claims, and
advanced WOT analysis remain deferred.
