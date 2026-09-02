# Architecture

## Intended data flow and ownership

```text
VehicleProfile + InitialConditions + Scenario + Environment + SimulationClock
                         -> Vehicle Model (authoritative VehicleState)
                         -> simulated ECUs (controller/ECU state)
                         -> binary CAN frames
                         -> CAN transport
                         -> RawCanFrame
                              +-> raw-CAN session artifact
                              +-> bounded Raw CAN Explorer
                              +-> DBC decoder
                         -> telemetry core
                         -> telemetry service
                         -> REST / WebSocket
                         -> Next.js engineering dashboard
                         -> future persistence / diagnostics
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
- **Python 3.12+:** synchronous live raw-CAN input, portable raw session recording/replay, bounded
  raw inspection, authoritative DBC decoding, immutable CAN metadata, deterministic telemetry
  aggregation, and a FastAPI REST/WebSocket application boundary. Python does not define or access
  C++ `VehicleState`.
- **TypeScript/Next.js:** observation-only operator visualization. Phase 5A owns network contract
  validation, ordered client state, presentation history, and engineering views; Phase 5B adds
  session metadata/replay controls through the same provider. It does not decode CAN or access
  vehicle state.
- **PostgreSQL:** future durable configuration, session indexing, decoded analytics, diagnostics,
  and analysis; currently local infrastructure only. Raw session artifacts intentionally remain
  filesystem-based in Phase 5B.
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
                                                                    |
                                                          TelemetryEngine
                                                    /          |          \
                                               latest      histories    snapshots
                                                                    |
                                                        TelemetryService
                                                          /          \
                                                        REST       WebSocket
                                                                    |
                                                        Next.js frontend
```

The packaged DBC remains authoritative. Python receives only arbitration ID, meaningful payload
bytes, and integer simulation timestamp; it neither imports nor mirrors `VehicleState`.
`tuneros_can_gateway` depends only on generic CAN, while the executable composes the gateway and
multi-ECU vehicle-network targets. The single-client server begins simulation after accept,
preserving time-zero frames. No telemetry service, physical CAN, broker, persistence, or frontend
path was added by Phase 2C itself.

## Telemetry boundary

Phase 4A begins exclusively at `DecodedCanFrame`. `TunerOsDbcDecoder` exposes immutable
library-independent DBC metadata, and `SignalCatalog` maps it into canonical semantic keys and
provenance. `TelemetryEngine` synchronously preserves frame arrival order, rejects backward
simulation timestamps, updates all signals from one frame atomically, and stores only latest samples,
bounded per-signal histories, and small statistics.

Raw CAN remains available before decode for the Phase 5B session recorder and Phase 6A explorer.
Telemetry never retains raw bytes and never accesses `VehicleState`. See
[Telemetry contracts](TELEMETRY.md).

## Raw CAN Explorer boundary

Phase 6A adds a second observation domain without widening telemetry:

```text
RawCanGatewayClient or SessionReader -> RawCanFrame
                                          +-> SessionRecorder (live only)
                                          +-> CanExplorer -> raw REST / raw WebSocket -> /can
                                          +-> DBC -> TelemetryEngine -> existing telemetry clients
```

`CanExplorer` receives the same raw object before telemetry decode, assigns its own source-local
sequence, annotates from immutable DBC metadata, and retains a bounded recent window plus per-ID
statistics. Unknown IDs and known-message decode failures remain raw observations. The explorer does
not own sockets, sessions, telemetry state, or source selection; `TelemetryService` coordinates the
live/replay tap and lock. Raw and decoded WebSockets remain distinct because their data volume,
failure policy, and consumers differ. See [Raw CAN Explorer](CAN_EXPLORER.md).

## Raw session boundary

Phase 5B taps the exact live object before decode:

```text
                        +-> SessionRecorder -> <uuid>.tuneros/{manifest.json, frames.bin}
RawCanGatewayClient ----+
                        +-> TunerOsDbcDecoder -> TelemetryEngine -> service/API/UI

session artifact -> SessionReader -> RawCanFrame -> TunerOsDbcDecoder
                 -> fresh TelemetryEngine -> same service/API/UI
```

Raw CAN is the canonical recording. The recorder does not reconstruct frames from decoded signals,
sort, deduplicate, normalize timestamps, or retain the run in memory. Replay validates file/DBC
hashes and regenerates all decoded state. Only one live or replay source can own a service engine at
once. See [Session recording and replay](SESSIONS.md).

## Telemetry service boundary

Phase 4B adds `TelemetryService` as an application coordinator around the existing gateway, decoder,
catalog, and engine. One dedicated thread performs blocking gateway ingestion. A service-owned lock
serializes engine mutation and coherent API reads; `TelemetryEngine` itself remains a synchronous,
deterministic domain object. FastAPI never decodes CAN or reproduces aggregation logic.

REST provides catalog and current/queryable domain state. WebSocket clients receive an immutable
initial snapshot followed by one decoded delta per accepted CAN frame. Per-client async queues are
bounded, so a slow client is disconnected without blocking ingestion or other clients. Normal
gateway EOF leaves final telemetry available in `COMPLETED`; gateway/decode/ingest exceptions become
`FAILED` without terminating the API process. See [API contracts](API.md).

## Frontend boundary

Phase 5A connects the browser directly to the local FastAPI boundary. Startup fetches REST status
and the authoritative catalog, while one shared WebSocket provides the initial telemetry snapshot,
ordered frame-atomic deltas, and terminal service state. The WebSocket snapshot replaces client
telemetry state before subsequent deltas are accepted, avoiding a REST-snapshot race.

The client validates critical network fields, keys observations by canonical message and signal
name, applies each decoded frame in one reducer transition, rejects duplicate/regressing sequence
numbers, and reports forward gaps. Its bounded, deterministically sampled chart history is disposable
presentation state, not recording or a new telemetry authority. Canonical units and full provenance
remain unchanged; km/h and percent appear only as display conversions. See
[Frontend dashboard](FRONTEND.md).

Phase 5B adds a Sessions view using the focused REST client and the existing provider. Replay resets
the provider with an authoritative empty WebSocket snapshot before frame-zero deltas, so prior live
state cannot mix with replay. The browser neither reads raw frame bytes nor opens a second replay
stream.

Phase 6A mounts a dedicated raw provider only on `/can`. Its bounded frame state and Freeze View are
disposable presentation concerns; neither changes source ingestion, recording, replay, simulator
state, or global decoded telemetry.
