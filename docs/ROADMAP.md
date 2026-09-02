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
| 2C | Live Raw CAN Gateway | **Complete** |
| 3A | Simulated DSC & Multi-ECU Shared Bus | **Complete** |
| 3B | Richer ECU & Network Behavior | Planned |
| 4A | Telemetry Core & Signal Aggregation | **Complete** |
| 4B | Live Telemetry Service/API | Planned |
| 5 | Telemetry Persistence & Sessions | Planned |
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

Phase 2C adds a version-one fixed-record binary protocol, loopback-only synchronous C++ TCP
transport/server and simulation executable, Python raw-frame client, compact live DBC consumer,
golden/stream tests, and an actual C++ to TCP to Python to DBC test. It preserves simulation
timestamps, IDs, DLC, payload bytes, and stream order without a telemetry service or wall pacing.

Phase 3A implements that boundary with two observation-only DSC frames, equal vehicle-derived wheel
speeds, independent integer-time ECU schedulers, global arbitration-ID sorting, combined exact
reset/replay, authoritative DBC additions, and unchanged raw gateway framing.

Phase 4A adds immutable DBC metadata views, stable semantic signal keys, typed/provenanced samples,
latest state, bounded histories, deterministic frame sequences, simulation-time freshness, coherent
snapshots, statistics, schema/order errors, exact reset replay, and live C++ gateway integration.

The recommended next step is Phase 4B, a narrowly scoped live telemetry service around the gateway,
decoder, catalog, and `TelemetryEngine`. REST snapshot/catalog endpoints and WebSocket updates can
then consume an established domain contract while persistence, sessions, diagnostics, and frontend
work remain deferred.

Further ECU behavior, physical CAN, diagnostics, calibration behavior, and frontend product work
remain later phases. A later phase begins only after its required contracts and authenticity
assumptions are documented and the preceding foundation remains testable.
