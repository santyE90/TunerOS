# Frontend dashboard

## Scope and boundary

Phase 5A establishes the observation-only Next.js 16, React 19, and TypeScript engineering
workstation. Phase 5B adds a Sessions view and replay source awareness. Overview presents selected
live or replayed engineering signals and trends; Telemetry inspects every decoded signal returned by
the backend catalog. Phase 6A adds a read-only Raw CAN Explorer at `/can`. Phase 7A adds a
REST-backed Diagnostics workspace at `/diagnostics`.

The browser consumes only FastAPI REST and WebSocket contracts:

```text
live gateway or raw session -> RawCanFrame -> DBC decode -> TelemetryService
                              -> coherent telemetry -> DiagnosticEngine
                              -> FastAPI -> Next.js views
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

## Raw CAN Explorer

The `/can` route mounts its own `CanExplorerProvider` and dedicated `/api/v1/ws/can` connection only
while that page exists. Raw history is not placed in `TelemetryProvider`, so Overview, Telemetry,
and Sessions do not rerender at raw-frame frequency. The initial raw snapshot is authoritative;
subsequent one-frame events carry raw sequence and updated statistics. Runtime validation covers
frames, decoded annotations, rates, source context, and all raw event envelopes.

The client retains at most 1,000 raw observations, bounds its animation-frame pending burst to the
same size, and renders at most 500 table rows. It rejects duplicate/regressing sequences and reports
forward gaps without reconstructing them. The page shows a compact per-ID rate table, raw frame
table, exact bytes, simulation timestamp, selected-frame detail, DBC engineering signals, and clear
unknown/decode-error states. ID, message, ECU/source, and payload/message text filters are local
presentation operations; React does not decode signal bitfields.

Follow live displays the newest retained rows first. Freeze View continues consuming into the
bounded current buffer while holding visible rows and selection stable. It counts passed frames and
reconciles to the latest bounded buffer on resume. It never pauses the backend, gateway, simulator,
recording, replay, or decoded telemetry. LIVE/REPLAY and replay session context come from the shared
backend source contract rather than URL inference.

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

## Diagnostics workspace

`/diagnostics` polls the bounded diagnostic REST contracts once per second while mounted; it does
not add a second high-rate socket or place diagnostics in `TelemetryProvider`. The summary identifies
live/replay source and backend lifecycle, reports authoritative simulation time, and displays counts
for every DTC lifecycle state. A status filter controls the deterministic DTC table, whose columns
include code, name, system, severity, status, first-detected/last-seen time, and occurrence count.

Selecting a DTC loads its rule metadata and immutable first-activation freeze frame. The detail view
shows confirmation/recovery durations, thresholds, timestamps, occurrence semantics, and the full
catalog-key-ordered signal snapshot with units, source ECU, CAN ID, frame sequence, and
sample timestamp. The event timeline displays retained transition events in sequence order. Clear is
available only for historical records; active and pending records remain visibly non-clearable. An
empty healthy run explicitly displays `No diagnostic trouble codes`. Presentation never derives a
health score, parses CAN, or reevaluates diagnostic rules.

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

Calibration and system tools remain labeled future navigation items. Sessions are filesystem-backed
metadata and full unpaced replay only. CAN Explorer is read-only, and Diagnostics is an observation
and historical-memory surface only: there is no fault-control UI, fault identity in browser
contracts, CAN transmission/editing, DBC editor, authentic BMW/OBD/UDS communication, warning
lamps, tune maps, scenario controls, authentication, PostgreSQL session or DTC indexing,
seek/scrub/playback speed, browser-side recording, or physical CAN functionality. Fault-altered
signals and resulting DTCs use these unchanged views naturally.

## Historical investigation workspace

Phase 8A adds `/sessions/[sessionId]/investigate` as a REST-only recorded-session workspace; it does
not use either live WebSocket or mutate provider/source state. Sessions links every complete,
compatible artifact to it. Diagnostics links replay-backed first-detection, confirmation, recovery,
and event timestamps using the explicit source session UUID. Live-only diagnostics explain that a
recorded session is required.

Validated URL state includes integer `t`, bounded `before`/`after`, optional `code`, up to six
canonical `signal` values, and optional `baseline`/`baseline_t`. An omitted center is resolved by the
backend and canonicalized into the URL. The page labels **Recorded session**, displays artifact
metadata and actual bounds, and synchronizes a native timeline, lightweight SVG telemetry plots,
diagnostic state/events, existing freeze-frame evidence, and local raw-CAN inspection.

The cursor is integer simulation time. Values are the latest exact observation at or before it,
without interpolation; raw frames within ±100 ms are filtered from the loaded response rather than
refetched during movement. Frame detail uses existing CAN formatting and backend annotations. A
compatible baseline uses an explicit center and shared relative-time chart axis; numeric sample
statistics and neutral DTC-presence wording add no anomaly or causality claim. **Export Evidence**
downloads deterministic backend JSON. See [Diagnostic investigation workflows](INVESTIGATION.md).
