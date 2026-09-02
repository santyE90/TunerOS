# Architecture

## Intended data flow and ownership

```text
VehicleProfile + InitialConditions + Scenario + Environment + SimulationClock
                         -> Vehicle Model (authoritative VehicleState)
                         -> simulated ECUs (controller/ECU state)
                         -> binary CAN frames
                         -> CAN transport
                         -> DBC decoder
                         -> telemetry backend
                         -> persistence / diagnostics / API
                         -> frontend
```

Simulation owns physical/logical state evolution. ECUs observe only relevant vehicle state, own
controller state, and publish selected information. Transport moves opaque frames. DBC decoding
assigns engineering meaning. Telemetry owns downstream observations and application history; the
frontend consumes backend contracts.

CAN is the telemetry source of truth outside the vehicle/ECU simulation boundary. The backend
and frontend must not read `VehicleState` directly, because doing so would hide the protocol,
decoding, timing, and provenance boundaries TunerOS is meant to teach. Tests and simulator-only
tooling may inspect `VehicleState` to validate vehicle evolution and encoding; this is development
access, not a production telemetry path.

## Engineering principles

- Optimize for learning and portfolio value, observable boundaries, and testability.
- Prefer believable internal consistency to OEM-perfect physics; TunerOS is not a digital twin.
- Do not reproduce or claim proprietary BMW software, tables, algorithms, or protocols.
- Public concepts may be modeled; realistic simplifications and synthetic behavior must be labeled.
- Prefer determinism to incidental randomness, and justify complexity by engineering value.
- Keep simulation independent of frontend and wall-clock scheduling.
- Never bypass a future boundary merely for implementation convenience.

## Language responsibilities

- **C++20:** authoritative deterministic vehicle-side contracts and vehicle state evolution,
  application-level Classic CAN primitives, and simulated ECU publication.
- **Python 3.12+:** future CAN adapters, decoding orchestration, telemetry ingestion, deterministic
  diagnostics, persistence, and HTTP/WebSocket services. It does not duplicate C++ `VehicleState`.
- **TypeScript/Next.js:** operator-facing visualization and investigation workflows only.
- **PostgreSQL:** future durable configuration, sessions, decoded telemetry, diagnostics, and
  analysis; currently local infrastructure only.
- **Docker Compose:** reproducible local infrastructure, currently PostgreSQL only.

Language-neutral artifacts belong in `shared/` only when real cross-language consumers exist. The
simulator does not invent code generation or mirror the vehicle model into Python.

## Simulation boundary

The authoritative simulation-time, unit, numerical, `VehicleState`, `VehicleProfile`, environment,
scenario, determinism, and configuration contracts are in
[Simulation contracts](SIMULATION_CONTRACTS.md). Phases 1A–1C implement the simulation clock,
reference profile factory, explicit initial conditions/environment, stateless scenario schedules for
IDLE/COLD_START/WARMUP/CITY, and minimal deterministic vehicle response. CITY adds only synthetic
longitudinal speed, scenario-controlled manual gear selection, and speed/gear/RPM coupling. It is not
a full drivetrain or vehicle-physics model. Phase 2A adds a read-only simulated DME publication
boundary and synthetic binary CAN frames without changing vehicle evolution.

## Transport abstraction

`tuneros_can` defines a generic Classic CAN frame plus synchronous transport contract without a
simulator dependency. Its Phase 2A `InMemoryTransport` is deterministic FIFO storage with no thread,
socket, latency, or arbitration simulation. `tuneros_dme` depends on both `tuneros_can` and
`tuneros_simulator`; the simulator does not depend on CAN, avoiding a cycle and preserving standalone
Phase 1 use. Later adapters may target SocketCAN or physical hardware without changing vehicle
evolution or DME packing.

`VehicleNetworkSimulation` coordinates vehicle ticks, read-only DME observation, publication, and
network reset. It does not expose a vehicle-to-telemetry shortcut. DBC decoding and all application
layers remain unimplemented.
