# Raw CAN Explorer

## Scope and architecture

Phase 6A adds a read-only engineering view of the exact synthetic `RawCanFrame` stream. It works at
the pre-decode boundary and never reconstructs bytes from telemetry:

```text
LIVE
RawCanGatewayClient
        +-> SessionRecorder
        +-> CanExplorer
        +-> TunerOsDbcDecoder -> TelemetryEngine

REPLAY
SessionReader
        +-> CanExplorer
        +-> same TunerOsDbcDecoder -> same TelemetryEngine
```

The explorer does not own sockets, recording, `TelemetryEngine`, simulation, or source selection.
`TelemetryService` coordinates one active live or replay source and presents separate raw and
decoded streams. All current traffic remains explicitly synthetic TunerOS simulation CAN.

## Observation model and buffer

`CanExplorer` is a synchronous domain object using the existing immutable `RawCanFrame`. Each
ingestion creates an immutable `CanExplorerFrame` containing:

- a raw observation sequence;
- the exact raw frame;
- DBC message name, transmitter, and expected period when known;
- decode status and optional error;
- immutable decoded engineering-value signals and their DBC units when decoding succeeds.

The default backend buffer retains the most recent 4,096 observations in a `deque`. Append order is
source arrival order; no sorting, timestamp normalization, deduplication, or resampling occurs.
Equal-timestamp frames and duplicates receive separate sequences. Overflow evicts only the oldest
inspection record. Per-ID counters remain bounded by the 2,048 possible standard 11-bit IDs.

Sequence starts at zero for each active source. Reset clears retained frames, next sequence, global
statistics, and per-ID statistics. Starting live ingestion or replay performs that reset, preventing
cross-run mixing. The helper is protected by the existing `TelemetryService` coordination lock.

## DBC annotation, unknown IDs, and decode errors

Names, transmitters, expected cycle times, signal names, values, and units come from the packaged
authoritative DBC abstraction. Explorer code has no ID-to-ECU lookup table and exports no
`canmatrix` object.

A valid standard frame whose ID is absent from the DBC remains a normal raw observation with
`decode_status: "unknown"`; message, source, expected period, and decoded signals are absent. A
known-ID frame that cannot decode—for example, because its DLC is wrong—remains visible with the
known metadata, `decode_status: "error"`, and a safe error description. The independent telemetry
path retains its stricter policy and may fail on that same frame. Raw evidence is never erased by a
decode failure.

API payloads contain meaningful bytes only:

```json
{
  "dlc": 5,
  "payload": [112, 23, 128, 64, 1],
  "payload_hex": "70 17 80 40 01"
}
```

Session padding beyond DLC is not exposed.

## Statistics and frequency

Global state reports retained frames, total observations since reset, unique IDs, oldest/newest
retained simulation timestamps, last raw sequence, and the shared live/replay source context.

Per ID, the explorer reports current retained count, lifetime count since source reset,
first/latest timestamps, latest DLC, optional DBC metadata, expected period, observed average period,
and observed frequency. For at least two frames:

```text
observed_average_period_us = (latest_timestamp_us - first_timestamp_us) / (count - 1)
observed_frequency_hz = 1,000,000 / observed_average_period_us
```

Frequency uses simulation time only. If fewer than two observations exist, both values are null. If
multiple observations have zero elapsed simulation time, the period is zero and frequency is null.
Expected-versus-observed values are descriptive and are not diagnostic thresholds or faults.

## REST API

Raw routes are separate from decoded telemetry:

| Route | Meaning |
| --- | --- |
| `GET /api/v1/can/frames` | Recent retained observations, oldest to newest |
| `GET /api/v1/can/frames/{sequence}` | Full retained observation detail; 404 after eviction/absence |
| `GET /api/v1/can/statistics` | Global bounded-buffer and source statistics |
| `GET /api/v1/can/messages` | Per-ID retained and lifetime statistics since source reset |

Frame queries default to 500 and permit at most 1,000 results. Optional exact backend filters are
`arbitration_id`, `message_name`, and `source_ecu`. An ID query uses the canonical integer; the API
response also supplies `0xNNN`. Results preserve their original order and a limit returns the most
recent matching tail, still oldest to newest.

## Raw WebSocket and backpressure

`WS /api/v1/ws/can` is active only for CAN Explorer consumers. It is deliberately separate from
`WS /api/v1/ws/telemetry`.

Events are:

- `initial_can_snapshot`: at most the latest 1,000 frames, global statistics, per-ID statistics,
  source context, and service state;
- `can_frame`: one immutable raw observation plus updated global and affected-ID statistics;
- `can_source_state`: source lifecycle, error, and live/replay context.

Subscription and snapshot capture occur under one service lock, so subsequent raw deltas cannot
race ahead of initialization. Raw sequence preserves arrival order. Live raw subscribers use a
bounded 32,768-event queue; replay raw subscribers use 65,536, enough for the current 27,305-frame
CITY replay burst. Overflow never silently drops an event: only the slow subscriber is disconnected
with code 1013 and reason `slow_client`. Ingestion, telemetry, and recording never block on a raw
client. Replay remains unpaced and contains no sleeps.

## Frontend design and Freeze View

`/can` mounts a dedicated `CanExplorerProvider`; the raw WebSocket is absent on other routes and raw
traffic is not stored in the global telemetry provider. Runtime guards validate all raw REST and
WebSocket contracts.

The page provides:

- shared LIVE/REPLAY source and optional replay-session context;
- compact message count/expected-rate/observed-rate summary;
- CAN ID, message, ECU, and payload/message filters;
- a dense sequence/time/ID/message/source/DLC/payload frame table;
- selected-frame raw metadata, decode status/error, exact bytes, and decoded engineering signals;
- Follow live ordering and presentation-only Freeze View.

The client retains at most 1,000 observations and renders at most 500 rows. Incoming bursts are
coalesced per animation frame with the pending set also bounded to 1,000. Duplicate/regressing raw
sequences are rejected and gaps are shown as inspection warnings; the browser does not reconstruct
missing data.

Freeze View keeps consuming into the bounded current buffer and tracks how many observations pass,
but leaves displayed rows and selection stable. Resume replaces displayed rows with the latest
bounded buffer. It does not pause the simulator, source, backend, recording, replay, or telemetry.

Phase 7B simulator-side faults naturally appear as changed bytes and decoded engineering values in
the existing explorer. The explorer receives no fault identifier, performs no fault-specific
decoding, and still cannot inject or edit frames.

## Deferred and prohibited behavior

Phase 6A does not transmit, edit, inject, or spoof CAN frames; edit decoded signals; upload/edit
DBCs; interpret anomalies or DTCs; access physical CAN; simulate arbitration/CRC/ACK; persist raw
browser history; or add replay pause, seek, scrub, speed, or wall-clock pacing.
