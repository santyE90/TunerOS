# Telemetry core

## Purpose and boundary

Phase 4A turns decoded synthetic CAN observations into deterministic, queryable application-domain
state. Its only ingestion contract is `DecodedCanFrame`:

```text
RawCanFrame -> TunerOsDbcDecoder -> DecodedCanFrame -> TelemetryEngine
```

The engine never accepts C++ simulator types, `VehicleState`, raw CAN, sockets, or `canmatrix`
objects. Raw frames remain independently available upstream for a future CAN explorer or recorder.
Telemetry contains no API, WebSocket, persistence, diagnostics, derived analytics, or presentation
conversion.

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
at 20,001 microseconds, while a 100 ms coolant signal remains fresh through 200 ms. Stale samples remain the
latest known values; freshness indicates update age only and carries no diagnostic meaning.

## Statistics and reset

Frozen `TelemetryStatistics` contains total accepted frames, total signal updates, latest simulation
timestamp, last frame sequence, and immutable counts by arbitration ID. It intentionally excludes
wall-clock rates and performance measurements.

`reset()` clears latest samples, histories, frame sequence, timestamp, and statistics while retaining
the immutable catalog. Reingesting an identical decoded-frame list produces exactly equal samples,
histories, snapshots, sequences, and statistics. This establishes replay readiness without adding a
session recording or replay feature.

## Errors and deferred work

- `TelemetrySchemaError`: decoded ID/message/signal metadata conflicts with the catalog, or semantic
  lookup is ambiguous.
- `OutOfOrderTelemetryError`: a frame timestamp moves backward relative to accepted live input.
- Duplicate and same-timestamp frames are not errors.

Explicitly deferred are FastAPI, WebSockets, PostgreSQL telemetry storage, session recording/replay,
diagnostics, thresholds, fault injection, derived horsepower/torque/boost/acceleration signals,
aliases, dashboards, and physical CAN.
