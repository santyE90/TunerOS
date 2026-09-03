# Diagnostic investigation workflows

## Purpose and boundary

Phase 8A connects recorded raw CAN, decoded telemetry, deterministic diagnostics, freeze frames,
and explicit session comparison around one integer simulation timestamp. It is read-only historical
analysis. A validated `.tuneros` raw-CAN artifact remains the only canonical recording; decoded
series, DTC state, and exports are rebuilt on demand and are not written beside or into the session.

```text
validated .tuneros -> SessionReader -> InvestigationService
                                      +-> ordered raw evidence
                                      +-> authoritative DBC
                                           -> isolated TelemetryEngine
                                           -> isolated DiagnosticEngine
                                      -> immutable InvestigationResult
```

This path is deliberately separate from active replay. Replay feeds a whole artifact through the
shared `TelemetryService` so the current-source UI behaves as it did live. Investigation scans one
artifact in an isolated engine and returns a bounded REST result; it does not reset, publish to, or
otherwise mutate the active service, its CAN Explorer, its diagnostics, or either WebSocket.

## Time and window semantics

`center_timestamp_microseconds` is unsigned integer simulation/session time. It is never browser,
wall-clock, arrival, or replay-processing time. If no center is supplied, the deterministic default
is the midpoint between the artifact's first and last timestamps. The default requested window is
2,000,000 microseconds before and after center. Before and after must be non-negative and their sum
may not exceed 30,000,000 microseconds.

Center must lie within the recorded timestamp range. Window edges that cross the first or last
recorded timestamp are clamped, and both requested spans and actual start/end are returned. A
comparison exposes independent actual primary and baseline windows; it does not imply equal
coverage near boundaries. A baseline center defaults to the primary center and is explicitly
clamped to the baseline range.

The service caps an allowed result at 8,192 raw frames and rejects a denser request with `413`
instead of silently truncating evidence. At most six unique canonical signals may be selected.
Restricting windows and signal count bounds output without downsampling observations.

## Streaming reconstruction and state at time

`SessionCatalog` resolves canonical UUIDs and enforces path containment. `SessionReader` validates
manifest completeness, installed DBC compatibility, frame hash, record count, DLC, timestamp order,
and the fixed session format. Investigation reuses that reader and streams artifact order; it does
not load the full raw frame set into a list. Current reconstructed state and diagnostic persistence
are maintained from the beginning, while only the requested raw frames, selected telemetry series,
events, and latest pre-window selected samples are retained.

Scanning from the beginning is necessary: a slow signal's latest value may precede the window, and
a diagnostic may already have accumulated confirmation/recovery persistence. `start_context`
contains the latest selected observation at or before the actual start. DTC state is captured after
all frames at or before center and reports each catalog rule as absent, pending, active, historical,
or cleared at that time—not its final-session status. Events retain `DiagnosticEngine` sequence and
artifact-time order. Existing immutable first-activation freeze frames are surfaced only when they
already existed at center; no replacement evidence is synthesized.

Raw frames retain artifact order, duplicates, equal timestamps, ID, DLC, and exact payload. Their
`sequence` is the zero-based artifact ordinal, independent of telemetry frame sequence. DBC
annotations and decoded signal values reuse `CanExplorer`. Telemetry series retain exact observed
sample timestamps and types; nothing is interpolated or resampled.

## Comparison and statistics

A user explicitly selects a baseline `.tuneros` session and center. Comparison requires the same
DBC SHA-256, synthetic CAN network identity, and vehicle profile. Both sessions are evaluated over
their own center-relative axes (`sample_time - center_time`). There is no wall-time alignment,
automatic event matching, byte-level CAN diff, significance test, anomaly score, or causal claim.

For each selected numeric series, summary data is observation count, first, last, minimum, maximum,
and the simple arithmetic sample mean; mean difference is primary minus baseline. Boolean series
retain first, last, count, and bounded distinct values without numeric coercion or a meaningless
mean. Catalog and requested signal ordering remain deterministic. When a DTC code is supplied, the
comparison neutrally reports whether that code has an event in each bounded window.

## REST and frontend workflow

The session-scoped routes are:

- `GET /api/v1/sessions/{uuid}/investigation`
- `GET /api/v1/sessions/{uuid}/investigation/compare`
- `GET /api/v1/sessions/{uuid}/investigation/export`

All accept `center_us`, `before_us`, `after_us`, repeated `signal=Message.Signal`, and optional
`code`. Compare requires `baseline_session_id` and accepts `baseline_center_us`; export accepts the
same optional baseline parameters. Invalid queries return `422`, incompatible or corrupt sessions
return `409`, unknown canonical UUIDs return `404`, and raw evidence beyond the cap returns `413`.

The `/sessions/[sessionId]/investigate` workspace uses REST only. It clearly labels the source as a
recorded session, displays metadata and actual bounds, and keeps center/window/baseline/signal state
in validated URL parameters. A timeline marks boundaries, center, diagnostic transitions, freeze
capture, and a local cursor. At the cursor, signal values use the latest exact observation at or
before the selected microsecond; charts do not interpolate. The already-loaded raw result supplies
the ±100 ms CAN table and selected-frame detail, so cursor movement creates no backend request.
Diagnostic rule `required_signals` seed useful plots, and selection is capped at six.

Sessions exposes Investigation separately from Replay. Diagnostics links first detection,
confirmation, recovery, and individual events when the active source is a replay with an explicit
session UUID. A live diagnostic without a safely finalized artifact instead asks the user to record
the run; no filename association is inferred.

## Deterministic evidence export and tradeoffs

The backend-generated download is JSON format `tuneros.diagnostic_investigation`, version 1. It
contains session metadata and identities, actual/query window, selected definitions and exact
series, pre-window context, bounded raw frames, DTC states/events, existing freeze frames,
statistics, and optional compatible baseline/comparison. It contains no filesystem path or volatile
wall-clock creation time. Identical artifacts and queries therefore serialize to equivalent
evidence. Export is generated on demand and never stored in the source artifact.

Phase 8A performs a correctness-first streaming scan from session start for each request. The known
105-second CITY regression artifact (27,305 frames and 93,467 decoded updates) remains practical,
while a persistent index would add invalidation, schema, and trust complexity prematurely. An index,
advanced waveform tooling, raw byte diff, PDF output, live-history caching, tuning, physical CAN,
and OEM diagnostic protocols remain deferred.

## Phase 8B tuning comparison

Session identity panels show calibration provenance for Primary and Baseline. Missing v1 identity is
**Unknown / Legacy**. Calibration equality is not required: supported DBC, CAN-network identity,
and vehicle-profile identity determine compatibility. Stage 1 WOT_PULL can therefore be compared
with Stock at explicit equal centers. Differences reconstruct from raw CAN; Investigation contains
no calibration model.
