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
- **Python 3.12+:** synchronous live raw-CAN gateway input and authoritative DBC decoding into typed
  engineering signals; future telemetry, diagnostics, persistence, and HTTP/WebSocket services begin
  downstream of this boundary. Python does not define or access C++ `VehicleState`.
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
boundary and synthetic binary CAN frames without changing vehicle evolution. Phase 3A adds an
independent read-only simulated DSC that derives equal wheel speeds from canonical vehicle speed;
it adds no redundant `VehicleState` fields or stability-control behavior.

## Transport abstraction

`tuneros_can` defines a generic Classic CAN frame plus synchronous transport contract without a
simulator dependency. Its Phase 2A `InMemoryTransport` is deterministic FIFO storage with no thread,
socket, latency, or arbitration simulation. `tuneros_dme` depends on both `tuneros_can` and
`tuneros_simulator`; `tuneros_dsc` has the same one-way dependencies, and
`tuneros_vehicle_network` composes both. The simulator does not depend on CAN, avoiding cycles and
preserving standalone Phase 1 use. Later adapters may target physical hardware without changing
vehicle evolution or ECU packing.

`VehicleNetworkPublisher` asks each ECU for due frames, combines them, sorts by ascending arbitration
ID, and sends through one shared transport. `VehicleNetworkSimulation` coordinates that publisher
with vehicle ticks, in-memory transport, and exact reset/replay. DME and DSC do not know about each
other or consume one another's frames. No vehicle-to-telemetry shortcut exists.

## Raw CAN process and Python decode boundary

Phase 2C makes raw CAN the live language/process boundary:

```text
C++ process: VehicleSimulation -> DME + DSC -> ordered CanFrame set -> TcpCanTransport
                                                       |
                   versioned binary TCP loopback raw-CAN boundary
                                                       |
Python process: RawCanGatewayClient -> RawCanFrame -> TunerOsDbcDecoder -> DecodedCanFrame
```

The packaged DBC remains authoritative. Python receives only arbitration ID, meaningful payload
bytes, and integer simulation timestamp; it neither imports nor mirrors `VehicleState`.
`tuneros_can_gateway` depends only on generic CAN, while the executable composes the gateway and
multi-ECU vehicle-network targets. The single-client server begins simulation after accept,
preserving time-zero frames. No telemetry service, physical CAN, broker, persistence, or frontend
path is added.
