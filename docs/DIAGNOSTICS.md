# Deterministic diagnostics and DTC lifecycle

## Scope, authority, and disclaimer

Phase 7A implements in-memory, rules-based diagnostics derived only from decoded engineering
telemetry:

```text
RawCanFrame -> authoritative DBC -> TelemetryEngine -> coherent TelemetrySnapshot
                                                        -> DiagnosticEngine
```

The engine never reads `VehicleState`, simulator/scenario identity, raw bytes, CAN IDs, or DBC
scaling. Rules reference canonical telemetry `SignalKey` values. Evaluation happens once after a
complete decoded frame has been atomically ingested.

Every code, threshold, persistence duration, description, and severity below is a synthetic
TunerOS educational assumption. None represents BMW, N54, DME, or DSC fault logic or threshold
fidelity. The `TUN-*` namespace deliberately avoids presenting the catalog as OEM or standardized
OBD-II behavior.

## Initial diagnostic catalog

Catalog order is authoritative for deterministic same-timestamp event order:

| Code | System | Severity | Activation | Confirmation | Recovery/hysteresis | Recovery duration |
| --- | --- | --- | --- | ---: | --- | ---: |
| `TUN-DME-001` | DME | Critical | Coolant > 115 degC | 5 s | Coolant <= 110 degC | 3 s |
| `TUN-DME-002` | DME | Critical | Oil > 135 degC | 5 s | Oil <= 130 degC | 3 s |
| `TUN-DME-003` | DME | Warning | Engine running and battery < 12.5 V | 3 s | Engine stopped or battery >= 13.0 V | 2 s |
| `TUN-DME-004` | DME | Warning | Engine running and MAP outside 10..250 kPa absolute | 2 s | Engine stopped or MAP within 15..240 kPa absolute | 2 s |
| `TUN-DSC-001` | DSC | Warning | Any wheel differs from vehicle speed by > 3.0 m/s | 1 s | Every wheel within 1.5 m/s | 1 s |

The catalog proves single-signal high thresholds, boolean-context and outside-range DME rules, and
a cross-message DSC plausibility rule. System ownership is explicit catalog metadata; it is never
inferred from CAN-ID ranges.

## Lifecycle and persistence

```text
first fresh violation -> PENDING -> ACTIVE -> HISTORICAL -> CLEARED
                              recurrence: HISTORICAL/CLEARED -> PENDING -> ACTIVE
```

- The first fresh violating evaluation creates `PENDING` and a `condition_detected` event.
- Confirmation occurs when the violation has spanned at least the exact configured number of
  simulation microseconds. Duplicate evaluations at one timestamp do not advance persistence.
- A pending condition that normalizes before confirmation is removed. It creates a
  `condition_cleared` event but leaves no historical DTC.
- `ACTIVE` remains latched through its recovery hysteresis band. Continuous fresh normal
  observations must span the recovery duration before transition to `HISTORICAL`.
- `HISTORICAL` never clears automatically. An explicit clear produces `CLEARED` and retains the
  record and evidence.
- A historical or cleared condition that violates again returns to pending. Confirmation increments
  occurrence count, preserves original first detection, updates latest confirmation, clears the
  prior resolved/cleared timestamp, and does not replace the original freeze frame.

Active and pending DTCs reject clear operations. Clearing an already-cleared DTC is idempotent and
does not add another event. Clear only changes diagnostic memory; it has no simulator, CAN,
telemetry, or session side effect.

## Missing and stale inputs

All required samples must exist and be `fresh` in the coherent snapshot. Missing data is unavailable,
not zero, and cannot start or confirm a condition. Stale input cannot confirm pending state. An
unavailable evaluation resets the continuous confirmation/recovery timer, while preserving the
external pending record or active DTC. Staleness alone never recovers an active DTC.

Cross-message rules use each signal's latest sample and retain its actual timestamp/provenance.
They do not claim simultaneous measurement.

## Events, snapshots, and reset

Meaningful transition events are `condition_detected`, `condition_cleared`, `dtc_confirmed`,
`dtc_recovered`, and `dtc_cleared`.

Sequence is `0, 1, 2, ...` per engine lifecycle. Rules are evaluated in catalog order, preserving
deterministic same-timestamp ordering. The event deque retains the latest 1,024 events by default;
lifetime event count and latest sequence remain available after eviction. Evaluations themselves are
not logged.

`DiagnosticSnapshot` is immutable and contains observation time, latest telemetry frame sequence,
catalog-ordered DTC records, event counts/sequence, and exact lifecycle counts. Before telemetry it
contains null timestamps and zero counts without a fabricated health score.

Reset clears rule timers, DTC records, events, freeze frames, counts, observation state, and returns
event sequence to zero. The immutable catalog remains. Starting replay resets diagnostics beside
`TelemetryEngine` and `CanExplorer`.

## Freeze frames

The first transition to `ACTIVE` captures one immutable freeze frame from the current
`TelemetrySnapshot`. It contains every currently observed sample (17 at most today), sorted by
canonical `SignalKey`, with engineering value, unit, source ECU, message/signal identity, CAN
provenance, signal timestamp, signal telemetry sequence, capture timestamp, and triggering telemetry
frame sequence. Unseen signals are omitted; no `VehicleState` or raw payload is included.

Later telemetry, recovery, recurrence, and clearing cannot mutate or destroy the primary freeze
frame.

## Service, replay, and persistence

Both live and replay use the same service call:

```text
decoded frame -> TelemetryEngine.ingest(frame) -> TelemetryEngine.snapshot()
                                               -> DiagnosticEngine.ingest(snapshot)
```

Raw `.tuneros` artifacts remain unchanged and contain no DTCs, events, rules, or freeze frames.
Replay regenerates diagnostics from raw frames through the same DBC and telemetry engine. Identical
input and rule software produce equal state, events, sequences, occurrences, and freeze frames.
Normal IDLE, COLD_START, WARMUP, and CITY are expected to remain free of DTCs.

## REST API and frontend

Phase 7A is REST-only:

| Route | Meaning |
| --- | --- |
| `GET /api/v1/diagnostics` | Summary, counts, event sequence, service and source context |
| `GET /api/v1/diagnostics/dtcs` | Catalog-ordered observed DTC records; optional `status` |
| `GET /api/v1/diagnostics/dtcs/{code}` | One observed DTC or 404 |
| `GET /api/v1/diagnostics/dtcs/{code}/freeze-frame` | Immutable activation evidence or 404 |
| `POST /api/v1/diagnostics/dtcs/{code}/clear` | Historical-to-cleared; active/pending return 409 |
| `GET /api/v1/diagnostics/events` | Recent transition tail, oldest to newest; bounded `limit` |

No diagnostic WebSocket was added. `/diagnostics` polls this small derived state while mounted,
without changing the existing telemetry or raw-CAN streams. It shows textual lifecycle counts, a
dense status-filtered DTC table, selected rule/timeline detail, immutable freeze-frame signals, and
per-DTC historical clear. The normal state says **No diagnostic trouble codes**.

## Intentionally deferred

Phase 7A adds no fault injection, authentic BMW diagnostics, OBD/UDS/ISO-TP requests, Mode 03/04,
diagnostic CAN traffic, MIL/CEL control, limp behavior, DTC persistence/database tables, session DTC
caches, health score, anomaly detection, machine learning, tuning, CAN transmission, or physical
CAN support.
