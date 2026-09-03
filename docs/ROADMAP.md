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
| 4B | Live Telemetry Service & API | **Complete** |
| 5A | First Live Engineering Dashboard | **Complete** |
| 5B | Raw CAN Session Recording & Deterministic Replay | **Complete** |
| 6A | Raw CAN Explorer | **Complete** |
| 7A | Diagnostics & DTC Foundation | **Complete** |
| 7B | Fault Injection & Diagnostic Validation | **Complete** |
| 8A | Diagnostic Investigation Workflows | **Complete** |
| 9 | Expanded Fault Library & Effects | Planned |
| 10 | Engine Model Expansion | Planned |
| 11 | Calibration & Tuning | Planned |
| 12 | Dyno Mode | Planned |
| 13 | Data Analytics | Planned |
| 14 | Predictive Diagnostics / ML | Planned |
| 15 | Physical CAN / OBD Readiness | Planned |
| 16 | Release / Portfolio Readiness | Planned |

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

Phase 4B adds a synchronized live pipeline coordinator, explicit lifecycle states, FastAPI app
factory/lifespan, versioned catalog/snapshot/signal/history/statistics routes, frame-atomic WebSocket
deltas, bounded per-client queues, clean completion/failure behavior, and actual C++ gateway through
REST/WebSocket validation. It adds no persistence, diagnostics, simulator controls, or frontend.

Phase 5A turns the Next.js shell into an observation-only engineering dashboard. It consumes REST
status/catalog plus one WebSocket initial snapshot and ordered frame deltas, retains bounded
simulation-time chart history, displays freshness and provenance, and provides Overview and
catalog-driven Telemetry pages. It adds no backend contract, persistence, raw CAN view, diagnostics,
tuning, sessions, or simulator controls.

Phase 5B records exact live `RawCanFrame` values before decoding into versioned, SHA-256-protected
filesystem artifacts. Complete sessions replay unpaced through the existing DBC, telemetry engine,
REST/WebSocket, and dashboard. Sessions are cataloged by UUID and visible in the frontend; partial
recordings remain explicitly incomplete and excluded from replay. No database, decoded canonical
recording, seek/pacing, deletion, export, or raw-frame UI is added.

Phase 6A adds a shared live/replay pre-decode observer, deterministic raw sequence, bounded backend
and browser buffers, DBC annotations with unknown/error preservation, simulation-time per-ID rates,
dedicated raw REST/WebSocket contracts, and a read-only `/can` engineering workspace with filters,
selected-frame detail, and presentation-only Freeze View.

Phase 7A adds a deterministic diagnostic catalog and engine after coherent telemetry aggregation,
five conservative synthetic `TUN-*` rules, simulation-time confirmation/recovery and hysteresis,
pending/active/historical/cleared lifecycle state, bounded ordered events, immutable first-activation
freeze frames, explicit historical clear, replay regeneration, narrow REST resources, and the
`/diagnostics` workspace. Normal implemented scenarios remain fault-free. Diagnostic state is not
persisted in canonical raw sessions, and no OEM diagnostic protocol or fault source is implied.

Phase 7B adds four fixed simulator-side synthetic faults, half-open simulation-time activation,
physical-versus-sensor observation separation, a CLI-only overlay independent of scenarios, and
end-to-end validation through unchanged CAN/DBC/telemetry/diagnostics/session contracts. Fault raw
sessions replay exact diagnostic state without persisting fault identity or derived DTC data.

Phase 8A adds isolated, bounded, session-first investigation: raw and decoded evidence, diagnostic
state at an integer simulation timestamp, freeze-frame/event correlation, local cursor inspection,
explicit healthy-session comparison, and deterministic JSON export. Version-one raw sessions remain
canonical and no active source is mutated.

The recommended next step is Phase 8B, Investigation Usability and Session Indexing Contracts. It
should first measure larger physical-CAN-like artifacts, then define a trustworthy optional index
and richer waveform navigation without changing canonical raw evidence or introducing tuning.

Further ECU behavior, physical CAN, authentic vehicle diagnostics, calibration behavior, and frontend product work
remain later phases. A later phase begins only after its required contracts and authenticity
assumptions are documented and the preceding foundation remains testable.
