# Roadmap

Status notation: **complete** is validated foundation; **planned** is not implemented.

| Phase | Scope | Status |
| --- | --- | --- |
| 0A | Repository Foundation & Engineering Scaffold | **Complete** |
| 0B | Engineering Contracts & Vehicle Specification | **Complete** |
| 1A | Deterministic Simulation Core | **Complete** |
| 1B | Initial Conditions & Thermal Scenario Expansion | **Complete** |
| 1C | First Moving-Vehicle Scenario | **Complete** |
| 2A | Virtual CAN Foundation & First DME Publication | **Complete** |
| 2B | DBC & Decoding Layer | **Complete** |
| 2C | Live CAN Gateway Boundary | Planned |
| 3 | ECU Systems Expansion | Planned |
| 4 | Vehicle Network & Signal Expansion | Planned |
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

Phase 1C adds CITY with time-varying accelerator/load input, deterministic longitudinal speed,
scenario-controlled forward gears, synthetic speed-to-RPM factors, two stops, and cross-step tests.
It remains a signal-generation model: clutch detail, torque curves, wheel physics, and boost are not
modeled.

Phase 2A adds the canonical Classic CAN frame, standard-ID/DLC validation, deterministic FIFO
transport, a read-only simulated DME, three explicitly synthetic binary signal layouts, timestamp-
based 100/50/10 Hz publication, and an end-to-end vehicle/network runner. It does not implement DBC,
physical CAN, telemetry, or scenario-specific DME behavior.

Phase 2B packages an authoritative synthetic DBC, validates a Python raw Classic CAN frame contract,
decodes all three DME messages into typed engineering-unit signals, enforces unknown-ID and exact-DLC
policies, and proves C++/DBC agreement with independent golden vectors. It adds no live gateway,
transport adapter, telemetry service, or direct Python access to `VehicleState`.

The recommended next step is Phase 2C: define a live raw-CAN gateway from C++ publication to Python,
preserve IDs/payloads/timestamps exactly, and feed decoded frames synchronously or through a minimal
stream boundary. Database, API, diagnostics, and UI work should remain out of scope for that phase.

Further ECU behavior, physical CAN, diagnostics, calibration behavior, and frontend product work
remain later phases. A later phase begins only after its required contracts and authenticity
assumptions are documented and the preceding foundation remains testable.
