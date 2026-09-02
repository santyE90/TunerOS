# Frontend dashboard

## Scope and boundary

Phase 5A establishes the observation-only Next.js 16, React 19, and TypeScript engineering
workstation. Phase 5B adds a Sessions view and replay source awareness. Overview presents selected
live or replayed engineering signals and trends; Telemetry inspects every decoded signal returned by
the backend catalog.

The browser consumes only FastAPI REST and WebSocket contracts:

```text
live gateway or raw session -> RawCanFrame -> DBC decode -> TelemetryService
                              -> FastAPI -> shared provider -> Next.js views
```

It does not read `VehicleState`, decode CAN, duplicate scaling, invent values, persist runs, or
control the simulator. Current reference-vehicle identity is static product context because no
vehicle-profile endpoint exists; it is visually separate from live telemetry.

## Configuration and local workflow

The client reads two public environment variables in one configuration module:

```dotenv
NEXT_PUBLIC_TUNEROS_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_TUNEROS_WS_URL=ws://127.0.0.1:8000
```

The WebSocket base is derived from the API URL when its variable is omitted. Copy
`frontend/.env.example` to `frontend/.env.local` only when overrides are required.

On Windows, after building the C++ targets, use three terminals for live telemetry:

```powershell
# Terminal 1, repository root
.\build\cpp\can\Debug\tuneros_gateway_sim.exe --scenario city --port 45800

# Terminal 2, repository root with .venv activated
python -m tuneros.api --gateway-port 45800 --port 8000

# Terminal 3
Set-Location frontend
npm run dev
```

Open `http://localhost:3000`. The simulator is deliberately unpaced, so the six simulated seconds
may arrive almost instantly. The UI does not delay or fabricate telemetry to make motion appear
real-time.

For replay, launch the backend with `python -m tuneros.api --replay-session <session-uuid>` and no
C++ process, or select a complete compatible capture on the Sessions page of an idle/completed API.

## Client architecture

`TelemetryProvider` owns one browser WebSocket and a pure reducer-backed state shared by all views.
At startup, REST status, source, and catalog requests run once. The Sessions view uses the focused
API client for validated catalog/detail requests and invokes replay through a provider action; it
does not create another telemetry channel. The catalog drives the complete Telemetry table;
Overview alone uses a centralized map of selected canonical signal keys. All critical REST/WebSocket
JSON crosses explicit runtime guards before entering trusted state.

The client keeps two independent lifecycle values:

- connection: `connecting`, `connected`, `disconnected`, or `error`;
- backend service: `stopped`, `connecting`, `running`, `completed`, or `failed`.

The status bar displays both, plus authoritative simulation time, latest frame sequence, and
observed DME/DSC sources. It also labels the source `live`, `recording`, or `replay` with the session
name when available. These source labels do not replace per-signal ECU provenance.

## Sessions and replay reset

`/sessions` lists only complete backend-validated artifacts; it contains no fixture or mock session
data. Selecting a row fetches immutable metadata including UUID, UTC creation time, scenario,
duration, frame count, format version, vehicle/network identity, first/last timestamps, and both
SHA-256 digests. A visible DBC match/mismatch label controls whether replay is available. No local
filesystem path crosses the API.

Starting replay calls the narrow session replay endpoint, marks the provider source as replay, and
reconnects its one shared WebSocket. The backend waits for that subscriber. Its first empty
`initial_snapshot` replaces all previous samples, chart seeds, statistics, observation time, and
frame sequence before replay deltas begin. This prevents stale live values or sequence numbers from
mixing with replay. Overview and Telemetry then render replay through their unchanged selectors and
components.

## Snapshot and ordered deltas

The WebSocket `initial_snapshot` is authoritative for telemetry initialization. It replaces latest
samples, chart seeds, statistics, observation timestamp, and accepted frame sequence. REST snapshot
support exists in the API module for focused consumers but is not raced against the live socket.

Each `telemetry_update` is queued and every event is applied in arrival order. All samples from one
decoded CAN frame enter state in one reducer transition. A partial DME or DSC event changes only its
present signals; signals at other update rates remain intact. Sequences older than or equal to the
accepted sequence are ignored with an integrity warning. Forward gaps are accepted and reported;
the client does not reorder or reconstruct events.

Unexpected socket closure retries after bounded delays of 0.5, 1, 2, 4, then 5 seconds. A terminal
`completed` or `failed` service event stops reconnect attempts. A new initial snapshot cleanly
re-establishes state and sequence.

## Chart state and presentation

Latest telemetry consumes every accepted event. Numeric chart buffers are deliberately separate,
disposable presentation state. Each signal retains at most 180 points and samples by authoritative
simulation time at 50,000-microsecond spacing. Updates inside one interval replace the interval's
last point so unpaced 100 Hz bursts do not create unbounded React rendering or memory use.

Charts use elapsed simulation seconds, restrained grids, explicit legends, and no wall-clock axis.
Overview separates RPM and speed because their units differ, groups coolant/oil/intake temperature,
and groups throttle/accelerator/load. A selected Telemetry row can show its recent local trend.

Canonical samples are never modified. Overview performs only these display conversions:

- vehicle and wheel speed: `km/h = m/s × 3.6`, with canonical m/s noted;
- normalized throttle/load/pedal values: `percent = value × 100`;
- timestamps: integer microseconds rendered as elapsed seconds.

The Telemetry page retains raw API values and units, full source ECU, message, API-supplied CAN ID,
timestamp, freshness, and expected period.

## State and failure presentation

Every observed metric includes textual `LIVE` or `STALE` state, its source, and original timestamp.
Never-observed signals render an em dash rather than zero. Stale samples retain their last values.

- Empty or unavailable backend: the shell renders with placeholders and explanatory status.
- Disconnected socket: last values remain visible while bounded reconnect is attempted.
- `completed`: final values and charts remain visible; the notice distinguishes simulation from
  replay completion.
- `failed`: last values remain visible with a concise backend failure message; traceback details are
  not rendered.

The dark visual system uses shared CSS tokens, tabular telemetry numerals, monospace only for
technical metadata, text in addition to color for state, semantic tables/articles/navigation, and a
reduced-motion rule. Dense desktop grids stack at smaller widths; navigation becomes horizontal and
the signal table scrolls rather than truncating engineering columns.

## Intentionally deferred

CAN Explorer, diagnostics, calibration, and system tools remain labeled future navigation items.
Sessions are filesystem-backed metadata and full unpaced replay only. There are no raw payload
tables, DTCs, warning lamps, tune maps, scenario controls, authentication, PostgreSQL session
indexing, seek/scrub/playback speed, browser-side recording, or physical CAN functionality.
