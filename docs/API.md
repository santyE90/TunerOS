# Telemetry, session, CAN, and diagnostics API

## Scope and startup

Phase 4B exposes the in-memory decoded telemetry domain to local REST and WebSocket consumers.
Phase 5B adds filesystem session catalog and replay coordination while preserving those telemetry
contracts. Phase 6A adds raw CAN inspection, and Phase 7A exposes deterministic diagnostics derived
from coherent telemetry snapshots. The API does not control the simulator, decode CAN itself, use
PostgreSQL, or authenticate users.
The API binds to `127.0.0.1:8000` by default; the raw gateway remains `127.0.0.1:45800`.

Windows development workflow from the repository root:

Terminal 1:

```powershell
.\build\cpp\can\Debug\tuneros_gateway_sim.exe --scenario city --port 45800
```

Terminal 2:

```powershell
.\.venv\Scripts\Activate.ps1
python -m tuneros.api --gateway-port 45800 --port 8000
```

Useful URLs:

- OpenAPI UI: `http://127.0.0.1:8000/docs`
- Status: `http://127.0.0.1:8000/api/v1/status`
- Catalog: `http://127.0.0.1:8000/api/v1/catalog`
- Snapshot: `http://127.0.0.1:8000/api/v1/telemetry`
- Source: `http://127.0.0.1:8000/api/v1/source`
- Sessions: `http://127.0.0.1:8000/api/v1/sessions`
- Diagnostics: `http://127.0.0.1:8000/api/v1/diagnostics`

CLI options configure API host/port, gateway host/port, telemetry and diagnostic history capacities,
and subscriber queue capacity. `--record-session` enables raw-first recording; `--session-name` and `--scenario` add
optional metadata. `--replay-session UUID` is mutually exclusive with recording and starts from the
configured session root without connecting to C++. `--session-root` or `TUNEROS_SESSION_ROOT`
selects that root. The C++ simulation and replay remain unpaced and may reach `COMPLETED` almost
immediately after a subscriber attaches.

## Service states and lifespan

`create_app()` performs no network I/O at import. Its lifespan starts a live `TelemetryService`, or
the selected initial replay, unless autostart is disabled or a test-controlled service is injected.
It stops and joins the worker on shutdown.

States are:

- `stopped`: not started or explicitly shut down;
- `connecting`: gateway connection is being established;
- `running`: gateway connected and frames are being consumed;
- `completed`: normal record-boundary EOF; final telemetry remains available;
- `failed`: connection/protocol/decode/ingest failure; safe error detail is available.

Phase 4B performs no retry or automatic scenario restart.

The separate source contract reports `live` or `replay`, replay session identity, whether an
optional live recorder is active, and its current raw-frame count. Source mode does not replace DBC
signal provenance. One service accepts only one connecting/running live or replay source.

## REST routes

All routes use integer simulation timestamps in microseconds and preserve literal DBC units and
transmitter names.

| Route | Meaning |
| --- | --- |
| `GET /api/v1/status` | Service state, connection flag, last error, latest timestamp, frame/update totals |
| `GET /api/v1/source` | Live/replay mode, replay session identity, and live recording state |
| `GET /api/v1/can/frames` | Bounded recent raw observations with optional ID/message/source filters |
| `GET /api/v1/can/frames/{sequence}` | One retained raw observation or 404 after eviction/absence |
| `GET /api/v1/can/statistics` | Raw buffer totals, sequence, timestamps, unique IDs, and shared source |
| `GET /api/v1/can/messages` | Per-ID retained/lifetime counts and simulation-time rates since source reset |
| `GET /api/v1/sessions` | Validated complete session summaries and installed-DBC compatibility |
| `GET /api/v1/sessions/{session_id}` | Validated complete manifest detail; accepts a canonical UUID only |
| `POST /api/v1/sessions/{session_id}/replay` | Reset telemetry and stage compatible raw replay; returns 202 |
| `GET /api/v1/catalog` | All DBC-derived `SignalDefinition` metadata |
| `GET /api/v1/telemetry` | Coherent latest snapshot with per-signal timestamps and freshness |
| `GET /api/v1/statistics` | Totals and explicit JSON-safe counts by CAN message |
| `GET /api/v1/signals/{signal_name}` | Unique semantic lookup; 404 absent, 409 ambiguous |
| `GET /api/v1/messages/{message_name}/signals/{signal_name}` | Unambiguous canonical lookup |
| `GET /api/v1/signals/{signal_name}/history` | Unique-name bounded history |
| `GET /api/v1/messages/{message_name}/signals/{signal_name}/history` | Canonical bounded history |
| `GET /api/v1/diagnostics` | Diagnostic counts, observation timestamp, event totals, and source/service context |
| `GET /api/v1/diagnostics/dtcs` | Catalog-ordered observed DTC records, optionally filtered by lifecycle `status` |
| `GET /api/v1/diagnostics/dtcs/{code}` | One observed DTC record; unknown or never-observed codes return 404 |
| `GET /api/v1/diagnostics/dtcs/{code}/freeze-frame` | Immutable first-activation evidence; absent evidence returns 404 |
| `POST /api/v1/diagnostics/dtcs/{code}/clear` | Clear one historical DTC; active or pending records return 409 |
| `GET /api/v1/diagnostics/events` | Bounded recent diagnostic transition tail in oldest-to-newest order |

History accepts optional positive `limit`. It may not exceed the configured engine capacity and
returns the most recent N retained samples in oldest-to-newest order. Invalid query values return
422. Catalog-known signals never observed return metadata with `sample: null` and `freshness: null`.

Example signal response:

```json
{
  "definition": {
    "key": {"message_name": "DscVehicleMotion", "signal_name": "VehicleSpeed"},
    "signal_name": "VehicleSpeed",
    "message_name": "DscVehicleMotion",
    "arbitration_id": 1312,
    "arbitration_id_hex": "0x520",
    "source_ecu": "TunerOsSimulatedDsc",
    "unit": "m/s",
    "expected_period_microseconds": 20000
  },
  "sample": {
    "key": {"message_name": "DscVehicleMotion", "signal_name": "VehicleSpeed"},
    "value": 1.25,
    "timestamp_microseconds": 6000000,
    "frame_sequence": 1563,
    "arbitration_id": 1312,
    "arbitration_id_hex": "0x520",
    "message_name": "DscVehicleMotion",
    "source_ecu": "TunerOsSimulatedDsc",
    "unit": "m/s",
    "freshness": "fresh"
  },
  "freshness": "fresh"
}
```

Boolean values remain JSON booleans and numerical values remain JSON numbers. CAN IDs are integers
with an additional consistently formatted hexadecimal field. Statistics use a list of message-count
objects rather than relying on JSON conversion of integer dictionary keys.

Diagnostic values use the same canonical engineering units and integer simulation timestamps as
telemetry. DTC status is one of `pending`, `active`, `historical`, or `cleared`; severity is `info`,
`warning`, or `critical`. `events?limit=N` defaults to 200 and is bounded to 1,024. A freeze frame
contains every signal observed in the coherent telemetry snapshot that first confirmed the DTC,
ordered by canonical message/signal key. Clearing is diagnostic-memory management only: it does not
modify the simulator, CAN, telemetry, or recorded session. Diagnostics have no WebSocket in Phase
7A; the existing telemetry and raw sockets are unchanged.

Raw frame responses keep bytes unambiguous as both an integer array and uppercase spaced hex, with
no padding beyond DLC. Known IDs include DBC-derived name, transmitter, expected period, and decoded
engineering-value signals. Unknown IDs use null metadata and `decode_status: "unknown"`. A valid
known-ID frame that fails DBC decode remains present with `decode_status: "error"` and safe detail.

`GET /api/v1/can/frames` returns oldest-to-newest order. `limit` defaults to 500 and is bounded to
1,000; it selects the most recent matching tail. Optional `arbitration_id` (integer 0–2047),
`message_name`, and `source_ecu` filters are deterministic exact matches. These routes never expose
session paths or raw-frame transmit controls.

## WebSocket contract

Connect to `WS /api/v1/ws/telemetry`. The server first sends one coherent initial snapshot:

```json
{
  "type": "initial_snapshot",
  "snapshot": {
    "observation_timestamp_microseconds": null,
    "last_frame_sequence": null,
    "signals": [],
    "statistics": {
      "total_frames": 0,
      "total_signal_updates": 0,
      "latest_timestamp_microseconds": null,
      "last_frame_sequence": null,
      "frames_by_message": []
    }
  }
}
```

Each subsequently accepted `DecodedCanFrame` produces exactly one delta containing only that
frame's decoded signals:

```json
{
  "type": "telemetry_update",
  "timestamp_microseconds": 10000,
  "frame_sequence": 5,
  "arbitration_id": 1280,
  "arbitration_id_hex": "0x500",
  "message_name": "DmeFastEngine",
  "source_ecu": "TunerOsSimulatedDme",
  "signals": []
}
```

Signals from one CAN frame remain together. Frame sequence preserves ingestion and same-timestamp bus
order. No raw payload bytes are sent. Multiple clients receive independent ordered streams from
their connection point. Replay uses this same contract: it first supplies an authoritative empty
snapshot from the freshly reset engine, then publishes frame-zero onward.

Lifecycle changes use:

```json
{"type": "service_state", "state": "completed", "error": null}
```

Completion closes normally with code 1000 after the event. Failure sends `state: "failed"` with safe
error text and closes with 1011. Each live client has a bounded queue of 256 frame events by default.
Unpaced replay uses a separately configurable bounded queue of 65,536 events by default. A queue
overflow removes only that slow client and closes it with code 1013 and reason `slow_client`; events
are not silently discarded and ingestion does not block.

## Raw CAN WebSocket

Connect to `WS /api/v1/ws/can`. This is a dedicated raw inspection stream; `/ws/telemetry` remains
decoded and unchanged. `initial_can_snapshot` carries at most the most recent 1,000 raw observations,
global raw statistics, per-ID statistics, shared source context, and service state. Every subsequent
source frame produces one `can_frame` event containing the immutable observation, current global
statistics, and updated statistics for that ID. Lifecycle uses `can_source_state`.

Raw sequence is source-local and independent of telemetry sequence, so unknown or decode-error
frames still occupy their arrival position. Each raw client is independently bounded: 32,768 events
for live and 65,536 for unpaced replay by default. Overflow closes only that client with code 1013
and `slow_client`; it does not block ingestion or silently discard frames within the connection.
Completion/failure terminal behavior matches the telemetry socket. See
[Raw CAN Explorer](CAN_EXPLORER.md).

## Local security and deferred functionality

Development CORS allows only `http://localhost:3000` and `http://127.0.0.1:3000`. Defaults are
loopback-only, but Phase 4B provides no authentication, authorization, or TLS and must not be treated
as a production deployment configuration.

Fault injection, authentic OBD/UDS diagnostics, tuning, CAN transmission, simulator control,
authentication, session database indexing, advanced playback controls, and physical CAN remain
deferred. Diagnostic state is in-memory and regenerated during replay; it is not added to raw
session artifacts. Phase 5B keeps raw payloads inside the session layer and exposes metadata rather
than filesystem paths. See
[Frontend dashboard](FRONTEND.md) and [Session recording and replay](SESSIONS.md).
