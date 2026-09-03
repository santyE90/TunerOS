# Telemetry core

## Purpose and boundary

Phase 4A turns decoded synthetic CAN observations into deterministic, queryable application-domain
state. Phase 4B coordinates that unchanged domain core with the live gateway and an API boundary.
Phase 5B supplies either live gateway frames or recorded raw frames to that same decode/engine path.
The engine's only ingestion contract remains `DecodedCanFrame`:

```text
RawCanFrame -> TunerOsDbcDecoder -> DecodedCanFrame -> TelemetryEngine
```

The engine never accepts C++ simulator types, `VehicleState`, raw CAN, sockets, or `canmatrix`
objects. Raw frames remain independently available upstream for the session recorder and Phase 6A
CAN Explorer.
The domain engine contains no API, WebSocket, persistence, diagnostics, derived analytics, or
presentation conversion.

## Authoritative metadata and signal identity

`TunerOsDbcDecoder.database_metadata` exposes immutable TunerOS-owned `CanDatabaseMetadata`,
`CanMessageMetadata`, and `CanSignalMetadata` values derived from the same loaded authoritative DBC.
No external `canmatrix` object crosses this boundary. Message transmitter, unit, and cycle time are
therefore available without a second hand-maintained table.

`SignalCatalog` converts CAN metadata into immutable `SignalDefinition` values. Canonical identity is:

```text
SignalKey(message_name, signal_name)
```

The CAN ID remains provenance rather than the primary consumer key. `find_unique_signal(name)` offers
semantic lookup when exactly one catalog signal has that name, returns `None` when absent, and raises
`TelemetrySchemaError` when ambiguous.

Literal DBC units remain unchanged: `rpm`, `normalized`, `boolean`, `kPa_abs`, `degC`, `V`, `m/s`,
and `gear`. Phase 4A performs no presentation-unit conversion.

## Samples, sequence, and provenance

Each frozen `SignalSample` contains its key, decoded float/int/bool value, integer simulation
timestamp, frame sequence, arbitration ID, message name, source ECU/transmitter, and unit. Signals
from one frame share timestamp, frame sequence, message, ID, and transmitter.

Frame sequence starts at zero, increments once per accepted decoded frame, and reflects arrival order.
Equal timestamps are valid and are not sorted. Duplicate frames are separate observations with new
sequence numbers. A timestamp older than the latest accepted global simulation timestamp raises
`OutOfOrderTelemetryError`; live input is never silently reordered.

Schema validation verifies the ID, its authoritative message name, and every supplied signal name
before any state mutation. This makes frame ingestion atomic. Raw length and payload validation remain
upstream in the CAN decoder.

## Latest state, snapshots, and absent signals

`latest(key)` returns the newest `SignalSample` or `None` when the catalog knows the signal but it has
never been seen. No missing value is fabricated as zero or NaN. `latest_all()` returns an immutable
copy of all observed latest samples.

`TelemetrySnapshot` is frozen and owns immutable copies of selected or all latest samples, their
freshness, and `TelemetryStatistics`. Its observation timestamp is the latest frame timestamp known
to the engine. Individual sample timestamps remain authoritative and can differ because CAN messages
publish at different rates. Future ingestion cannot change an existing snapshot.

## Bounded history

Every observed signal has an independent `deque(maxlen=capacity)`. Capacity is one positive integer
per engine, defaults to 256, and rejects booleans, zero, and negative values. `history(key)` returns an
immutable tuple ordered oldest to newest. Each update is retained without averaging, interpolation,
resampling, or compression until capacity eviction removes the oldest sample. No decoded frames or
raw bytes are retained separately.

## Freshness

Freshness uses simulation time only. Each signal inherits its expected period from its DBC message:

```text
age_us = snapshot_time_us - sample.timestamp_microseconds
fresh when age_us <= 2 * expected_period_us
stale when age_us > 2 * expected_period_us
```

The centralized multiplier is two. Thus a 10 ms engine-speed signal is fresh through 20 ms and stale
at 20,001 microseconds, while a 100 ms coolant signal remains fresh through 200 ms. Stale samples
remain the latest known values; freshness indicates update age only and carries no diagnostic
meaning.

## Live service and concurrency

`TelemetryService` composes `RawCanGatewayClient`, `TunerOsDbcDecoder`, and `TelemetryEngine` without
merging their responsibilities. Its configuration contains gateway host/port, history capacity,
live and replay subscriber queue capacities, and gateway connection timeout. Defaults are
`127.0.0.1:45800`, 256 history samples, 256 queued live events, 65,536 queued replay events, and a
10-second connection timeout.

The blocking gateway reader or unpaced replay iterator runs on one dedicated daemon thread. A
re-entrant service lock protects
engine ingestion, lifecycle state, and coherent snapshot/history/statistics reads. Broadcasting
occurs only after a whole decoded frame has been accepted. The engine remains intentionally unaware
of threads and async consumers.

For live recording, the service sends the actual `RawCanFrame` to `SessionRecorder` before DBC
decode. For replay, `SessionReader` lazily yields `RawCanFrame` into the existing decoder. The
service reports `LIVE` or `REPLAY`, prevents concurrent sources, resets the engine before replay,
and retains DBC transmitter provenance unchanged.

Lifecycle states are `STOPPED`, `CONNECTING`, `RUNNING`, `COMPLETED`, and `FAILED`. Record-boundary
EOF is normal completion: final telemetry remains queryable and connected WebSockets receive a
completion event before closing normally. Connection, protocol, decode, or ingestion exceptions set
`FAILED`, preserve safe error text, notify clients, and do not crash the API process. There is no
automatic retry or restart in Phase 4B.

Each WebSocket subscriber owns a bounded `asyncio.Queue`. Worker-thread publications are scheduled
onto the subscriber's event loop in original frame-sequence order. If its queue fills, only that slow
subscriber is removed, receives an internal `slow_client` closure signal, and closes with WebSocket
code 1013. Updates are never silently dropped and one slow client cannot block ingestion. The larger
bounded replay default accommodates the current unpaced full CITY artifact without weakening the
smaller live backpressure policy.

The HTTP/WebSocket representation is defined separately in [API contracts](API.md). API adapters
copy immutable domain values into explicit Pydantic schemas; domain models were not changed for JSON.

## Statistics and reset

Frozen `TelemetryStatistics` contains total accepted frames, total signal updates, latest simulation
timestamp, last frame sequence, and immutable counts by arbitration ID. It intentionally excludes
wall-clock rates and performance measurements.

`reset()` clears latest samples, histories, frame sequence, timestamp, and statistics while retaining
the immutable catalog. Reingesting an identical decoded-frame list produces exactly equal samples,
histories, snapshots, sequences, and statistics. Phase 5B uses this reset before each replay; the
first WebSocket subscriber receives the resulting authoritative empty snapshot before replay starts.

## Errors and deferred work

- `TelemetrySchemaError`: decoded ID/message/signal metadata conflicts with the catalog, or semantic
  lookup is ambiguous.
- `OutOfOrderTelemetryError`: a frame timestamp moves backward relative to accepted live input.
- Duplicate and same-timestamp frames are not errors.

Explicitly deferred are PostgreSQL telemetry/session indexing, playback pacing and seek controls,
diagnostics, thresholds, fault injection, derived horsepower/torque/boost/acceleration signals,
aliases, authentication, and physical CAN. Phase 5B adds raw recording and deterministic replay
around this core without changing its decoded-frame ingestion contract. See
[Session recording and replay](SESSIONS.md).

Phase 6A also leaves this contract unchanged. `CanExplorer` observes each source `RawCanFrame`
before decoder/engine ingestion and uses a separate REST/WebSocket representation; raw bytes never
enter `TelemetryEngine` or `SignalSample`. See [Raw CAN Explorer](CAN_EXPLORER.md).

Phase 7A consumes the coherent snapshot only after a complete `DecodedCanFrame` has been ingested.
`DiagnosticEngine` reuses canonical `SignalKey`, engineering values, simulation timestamps,
freshness, and provenance; it does not alter telemetry latest/history/statistics or accept raw CAN.
See [Diagnostics](DIAGNOSTICS.md).

Phase 7B does not add a telemetry fault channel or metadata field. Altered engineering values arrive
only by decoding existing fault-affected raw frames. Signal keys, provenance, freshness, histories,
statistics, and REST/WebSocket contracts are unchanged.

Phase 8A reconstructs selected historical telemetry series from validated raw session frames for a
bounded investigation window. The authoritative DBC and production `TelemetryEngine` are reused in
an isolated service. Exact observation timestamps and types are retained, the latest selected
sample at or before window start is supplied as context, and no samples are interpolated,
downsampled, or persisted as a second telemetry recording. See
[Diagnostic investigation workflows](INVESTIGATION.md).

## Phase 8B WOT observations

The DBC catalog adds Lambda and IgnitionTiming from WOT-only `DmeCombustionObservation`. They use
the existing sample, provenance, history, freshness, replay, and investigation contracts. MAP and
vehicle speed expose further profile response. Telemetry never reads calibration profiles and
normal CITY still yields 93,467 updates.
