# Raw CAN session recording and replay

## Scope and authority

Phase 5B records the exact `RawCanFrame` stream received from the C++ gateway. Raw CAN is the
canonical session data; decoded signals, telemetry snapshots, chart points, and `VehicleState` are
not persisted. This keeps replay on the production observation path:

```text
LIVE
C++ VehicleSimulation -> DME + DSC -> RawCanGatewayClient
                                             |
                                             +-> SessionRecorder
                                             |
                                             +-> TunerOsDbcDecoder -> TelemetryEngine
                                                                       -> REST/WebSocket -> frontend

REPLAY
<uuid>.tuneros -> SessionReader -> RawCanFrame -> same TunerOsDbcDecoder
                                                    -> fresh TelemetryEngine
                                                    -> same REST/WebSocket -> same frontend
```

Phase 6A additionally sends each live or replay `RawCanFrame` through the bounded `CanExplorer`
before the unchanged telemetry decode. This does not alter the version-one artifact.

Phase 7A evaluates the same decoded telemetry through `DiagnosticEngine`. DTCs, transition events,
and freeze frames are regenerated during replay and are not fields or files in the artifact.

Phase 7B fault runs are recorded identically to normal runs. Neither fault identity/configuration nor
derived diagnostic state is added to the manifest or frame stream. After the C++ simulator stops,
the raw frames alone reproduce the same telemetry snapshot/histories/statistics, CAN Explorer state,
DTC snapshot/events, and freeze frame. Replay therefore neither knows nor needs the originating
fault ID.

Recording occurs before decode. It preserves arrival order, duplicate frames, equal timestamps,
arbitration ID, DLC, meaningful payload bytes, and unsigned integer simulation timestamps exactly.
Backward timestamps are rejected. Replay does not reconstruct raw frames from decoded data.

## Version-one artifact

Each complete portable artifact is a directory:

```text
<session-uuid>.tuneros/
├── manifest.json
└── frames.bin
```

The format name is `tuneros.raw_can_session` and its version is `1`. `frames.bin` begins with this
portable eight-byte header:

| Offset | Size | Encoding | Meaning |
| ---: | ---: | --- | --- |
| 0 | 4 | bytes | ASCII magic `TNSR` |
| 4 | 1 | unsigned integer | format version `1` |
| 5 | 3 | bytes | reserved, all zero |

Every following record is exactly 19 bytes. Multibyte integers use network byte order (big-endian),
so the format has no native padding or platform dependency:

| Offset | Size | Encoding | Meaning |
| ---: | ---: | --- | --- |
| 0 | 8 | unsigned 64-bit | simulation timestamp, microseconds |
| 8 | 2 | unsigned 16-bit | standard 11-bit CAN arbitration ID |
| 10 | 1 | unsigned 8-bit | Classic CAN DLC, 0–8 |
| 11 | 8 | bytes | payload, zero-padded after the DLC |

Python `struct` notation is `!QHB8s`. This is an explicit codec, not pickle, a native structure
dump, or persisted decoded telemetry.

## Manifest schema

`manifest.json` has a strict, closed schema; unknown or missing fields fail validation:

| Field | Type | Meaning |
| --- | --- | --- |
| `format_name` | string | `tuneros.raw_can_session` |
| `format_version` | integer | `1` |
| `session_id` | string | canonical UUID matching the artifact name |
| `created_at_utc` | string | recording creation time in UTC |
| `name` | string or null | optional normalized operator label |
| `scenario` | string or null | optional supplied scenario metadata |
| `vehicle_profile_id` | string | stable E90/N54 reference-profile identifier |
| `can_network` | string | synthetic CAN network identity |
| `dbc_name` | string | authoritative DBC filename |
| `dbc_sha256` | string | lowercase SHA-256 of that DBC at record time |
| `frames_sha256` | string or null | SHA-256 of the complete `frames.bin`, including its header |
| `status` | string | `recording`, `complete`, or `incomplete` |
| `failure_reason` | string or null | bounded failure description for an incomplete recording |
| `frame_count` | integer | number of 19-byte frame records |
| `first_timestamp_microseconds` | integer or null | first raw-frame timestamp |
| `last_timestamp_microseconds` | integer or null | last raw-frame timestamp |
| `duration_microseconds` | integer | last timestamp minus first, or zero when empty |

The scenario field is metadata supplied at launch; it is not inferred from traffic. These artifacts
contain the synthetic TunerOS network and are not authentic BMW captures.

## Recording lifecycle

`SessionRecorder` creates `<uuid>.partial/`, writes the header immediately, and appends one encoded
record per received frame. It keeps only counters, timestamps, and an incremental SHA-256 state in
memory. The manifest is initially `recording`.

On normal gateway record-boundary EOF, the recorder flushes and fsyncs `frames.bin`, writes a
`complete` manifest atomically, then atomically renames the directory to `<uuid>.tuneros/`. On a
connection, protocol, decode, ingestion, explicit-stop, or write failure, it closes the stream and
leaves an `incomplete` manifest inside the `.partial` directory. Partial artifacts are retained for
deliberate investigation but are not cataloged or replayable as complete sessions. Recording is
opt-in; a normal API launch writes no session files.

## Validation, integrity, and compatibility

`SessionReader` accepts only a complete manifest. Integrity validation streams the file and checks:

- header magic, version, and reserved bytes;
- full 19-byte records, standard IDs, and DLC limits;
- nondecreasing timestamps while preserving equal timestamps;
- exact frame count and first/last manifest timestamps;
- the SHA-256 of the complete frame file.

`frames()` is a generator and does not load a session into memory. It performs the same checks as it
is consumed; count, terminal timestamp, and hash validation necessarily finish when iteration is
exhausted. Call `validate_integrity()` when validation must complete before consuming frames.

The catalog validates complete artifacts before exposing them. API lookup accepts only a canonical
UUID and resolves only the matching `.tuneros` child inside the configured root; neither API model
contains a filesystem path. A DBC hash mismatch is visible in session metadata and blocks replay.
TunerOS does not attempt best-effort decoding with a different schema.

## Replay and source semantics

Replay creates a fresh `TelemetryEngine`, reads raw frames lazily, decodes each with the installed
authoritative `TunerOsDbcDecoder`, and ingests the resulting `DecodedCanFrame`. Identical artifacts
and software therefore reproduce exact frame sequences, snapshots, statistics, and bounded
histories. The telemetry service identifies its source as `live` or `replay` while preserving DBC
transmitter provenance such as `TunerOsSimulatedDme` and `TunerOsSimulatedDsc`.

One `TelemetryService` permits only one active source. A replay cannot start while live ingestion or
another replay is connecting/running, and the engine is reset before replay begins. The replay
worker waits for its first WebSocket subscriber when started through the CLI or API. That subscriber
first receives an authoritative empty snapshot, which clears old values, histories, statistics,
and frame sequence before frame-zero replay deltas arrive.

Replay is intentionally unpaced: simulation timestamps are preserved but do not cause wall-clock
sleeps. Live clients retain their 256-event bounded queues. Replay uses a separate bounded default
of 65,536 events so the current full CITY artifact can be delivered as an unpaced burst. Overflow
never silently drops updates: only the slow subscriber is disconnected with WebSocket code 1013
and reason `slow_client`, without blocking ingestion.

## Storage and workflows

The default root is `data/sessions`, which is ignored by Git. Override it with
`TUNEROS_SESSION_ROOT` or `--session-root`.

Record an existing live gateway run:

```powershell
python -m tuneros.api --gateway-port 45800 --record-session `
  --session-name "CITY baseline" --scenario city
```

Replay a complete compatible artifact without a C++ process:

```powershell
python -m tuneros.api --replay-session <session-uuid>
```

Alternatively, with the API already idle or completed, use
`POST /api/v1/sessions/{session_id}/replay`. In the frontend, open **Sessions**, inspect the capture
metadata and DBC status, select **Replay session**, and return to Overview through the shared
telemetry provider. List and detail are available from `GET /api/v1/sessions` and
`GET /api/v1/sessions/{session_id}`.

## Deliberately deferred

The implemented Raw CAN Explorer remains read-only and bounded. Session playback still has no
wall-clock pacing, pause, seek, scrub, playback-rate control, CSV export, persisted diagnostics, database
indexing, PostgreSQL session storage, or browser-side recording. Those are separate future
boundaries.

## Replay versus investigation

Replay and investigation consume the same validated version-one raw artifact for different purposes.
Replay resets the active `TelemetryService` and reproduces the entire source through the existing
telemetry, CAN, diagnostic, REST, and WebSocket views. Investigation leaves that service unchanged:
an isolated `InvestigationService` streams from session start, reconstructs DBC telemetry and
diagnostic persistence, and returns only a bounded window around an integer simulation timestamp.
The Sessions page therefore offers separate **Replay session** and **Investigate session** actions.
Investigation never writes an export or decoded sidecar into `.tuneros`; see
[Diagnostic investigation workflows](INVESTIGATION.md).

## Phase 8B version two provenance

Version 1 remains the legacy raw-CAN schema above and displays **Unknown / Legacy**; it is not
silently called Stock. When profile ID and positive revision are supplied, the recorder creates
version 2: its header version byte is `2`, and its strict manifest adds `calibration_id` and
`calibration_revision`. The 19-byte frame records and hashes are unchanged. Readers require
manifest/header agreement and accept both. The current additive DBC also accepts the known Phase 8A
DBC hash because no old layout changed. Both versions replay/investigate from canonical raw frames;
provenance is metadata, not persisted decoded state.
