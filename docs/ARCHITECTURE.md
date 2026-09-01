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

CAN will be the telemetry source of truth outside the vehicle/ECU simulation boundary. The backend
and frontend must not read `VehicleState` directly, because doing so would hide the protocol,
decoding, timing, and provenance boundaries TunerOS is meant to teach. Before CAN exists, Phase 1
tests and simulator-only tooling may inspect `VehicleState`; this exception is temporary development
access, not a future production path.

## Engineering principles

- Optimize for learning and portfolio value, observable boundaries, and testability.
- Prefer believable internal consistency to OEM-perfect physics; TunerOS is not a digital twin.
- Do not reproduce or claim proprietary BMW software, tables, algorithms, or protocols.
- Public concepts may be modeled; realistic simplifications and synthetic behavior must be labeled.
- Prefer determinism to incidental randomness, and justify complexity by engineering value.
- Keep simulation independent of frontend and wall-clock scheduling.
- Never bypass a future boundary merely for implementation convenience.

## Language responsibilities

- **C++20:** authoritative deterministic vehicle-side contracts and vehicle state evolution.
  Simulated ECU behavior remains future work.
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
a full drivetrain or vehicle-physics model. ECUs, CAN, telemetry, and diagnostics remain absent.

## Transport abstraction

A future CAN transport interface will separate producers/consumers from the mechanism carrying a
timestamped opaque frame. The first implementation can be in-process or Windows-friendly. Later
adapters may target SocketCAN or physical CAN hardware without changing simulation, decoding, or
application layers. Phase 1C does not design or implement this interface.
