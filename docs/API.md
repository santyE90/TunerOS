# Live telemetry API

## Scope and startup

Phase 4B exposes the in-memory decoded telemetry domain to local REST and WebSocket consumers. It
does not control the simulator, decode CAN, persist data, run diagnostics, or authenticate users.
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

CLI options configure API host/port, gateway host/port, history capacity, and subscriber queue
capacity. The C++ simulation remains unpaced and may reach `COMPLETED` almost immediately.

## Service states and lifespan

`create_app()` performs no network I/O at import. Its lifespan starts `TelemetryService` unless
autostart is disabled or a test-controlled service is injected, and stops/joins the worker on
shutdown.

States are:

- `stopped`: not started or explicitly shut down;
- `connecting`: gateway connection is being established;
- `running`: gateway connected and frames are being consumed;
- `completed`: normal record-boundary EOF; final telemetry remains available;
- `failed`: connection/protocol/decode/ingest failure; safe error detail is available.

Phase 4B performs no retry or automatic scenario restart.

## REST routes

All routes use integer simulation timestamps in microseconds and preserve literal DBC units and
transmitter names.

| Route | Meaning |
| --- | --- |
| `GET /api/v1/status` | Service state, connection flag, last error, latest timestamp, frame/update totals |
| `GET /api/v1/catalog` | All DBC-derived `SignalDefinition` metadata |
| `GET /api/v1/telemetry` | Coherent latest snapshot with per-signal timestamps and freshness |
| `GET /api/v1/statistics` | Totals and explicit JSON-safe counts by CAN message |
| `GET /api/v1/signals/{signal_name}` | Unique semantic lookup; 404 absent, 409 ambiguous |
| `GET /api/v1/messages/{message_name}/signals/{signal_name}` | Unambiguous canonical lookup |
| `GET /api/v1/signals/{signal_name}/history` | Unique-name bounded history |
| `GET /api/v1/messages/{message_name}/signals/{signal_name}/history` | Canonical bounded history |

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
their connection point.

Lifecycle changes use:

```json
{"type": "service_state", "state": "completed", "error": null}
```

Completion closes normally with code 1000 after the event. Failure sends `state: "failed"` with safe
error text and closes with 1011. Each client has a bounded queue of 256 frame events by default. A
queue overflow removes only that slow client and closes it with code 1013 and reason `slow_client`;
events are not silently discarded.

## Local security and deferred functionality

Development CORS allows only `http://localhost:3000` and `http://127.0.0.1:3000`. Defaults are
loopback-only, but Phase 4B provides no authentication, authorization, or TLS and must not be treated
as a production deployment configuration.

Persistence, session recording/replay, diagnostics, tuning, raw-CAN streaming, simulator control,
frontend telemetry, and physical CAN remain deferred.
