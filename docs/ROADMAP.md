# Roadmap

Status notation: **complete** is validated foundation; **planned** is not implemented.

| Phase | Scope | Status |
| --- | --- | --- |
| 0A | Repository Foundation & Engineering Scaffold | **Complete** |
| 0B | Engineering Contracts & Vehicle Specification | **Complete** |
| 1A | Deterministic Simulation Core | **Complete** |
| 1B | Initial Conditions & Thermal Scenario Expansion | **Complete** |
| 1C | First Moving-Vehicle Scenario | Planned |
| 2 | Virtual CAN Network | Planned |
| 3 | ECU Systems | Planned |
| 4 | DBC & Signal Layer | Planned |
| 5 | Telemetry Backend | Planned |
| 6 | Live Vehicle Dashboard | Planned |
| 7 | CAN Explorer | Planned |
| 8 | Drive Sessions & Replay | Planned |
| 9 | Diagnostics & DTCs | Planned |
| 10 | Fault Injection | Planned |
| 11 | Engine Model Expansion | Planned |
| 12 | Calibration & Tuning | Planned |
| 13 | Dyno Mode | Planned |
| 14 | Data Analytics | Planned |
| 15 | Predictive Diagnostics / ML | Planned |
| 16 | Physical CAN / OBD Readiness | Planned |
| 17 | Release / Portfolio Readiness | Planned |

Phase 1A implements the first deterministic vehicle core:

- fixed-step `SimulationClock` progression, pause, reset, duration, and tests;
- reference E90/N54 `VehicleProfile` factory;
- IDLE scenario inputs separated from vehicle response;
- internally consistent RPM, stationary vehicle, thermal, intake-air, and voltage evolution;
- deterministic state-sequence, alternate-step, and invariant tests.

Phase 1B adds explicit initial-condition/environment configuration, stateless time-derived scenario
inputs, `COLD_START`, `WARMUP`, exact reset/replay behavior, and long-run/cross-step tests.

Phase 1C may add the first moving-vehicle scenario with simplified speed and gear behavior,
time-varying accelerator/load input, and the minimum drivetrain abstraction needed to relate them.
It should remain deterministic and vehicle-side; clutch detail, wheel physics, ECU, and CAN work
stay out of scope until their later phases.

CAN, ECU publication, diagnostics, calibration behavior, and frontend product work remain later
phases. A later phase begins only after its required contracts and authenticity assumptions are
documented and the preceding foundation remains testable.
