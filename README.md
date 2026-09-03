# TunerOS

TunerOS is a BMW-focused automotive software engineering platform in its early simulation phase. Its
long-term purpose is to make simulated vehicle behavior observable through the same boundaries an
automotive telemetry system would use: ECUs, binary CAN frames, decoded signals, backend services,
and a browser interface. The first reference vehicle is a 2010 BMW E90 335i with the N54
engine.

> **Current status:** Phase 0, Phases 1A–1C, Phases 2A–2C, Phase 3A, Phases 4A–4B,
> Phases 5A–5B, Phase 6A, and Phase 7A are complete. C++ provides
> deterministic vehicle simulation, independent simulated DME and DSC publication, globally ordered
> synthetic Classic CAN, and in-memory transport. A versioned binary TCP loopback gateway carries
> the combined raw bus live into
> Python, which validates and decodes them through the packaged authoritative synthetic DBC. A
> synchronous telemetry core maintains typed latest values, provenance, bounded histories,
> immutable snapshots, statistics, and simulation-time freshness. A local FastAPI service exposes
> that domain through REST and frame-atomic WebSocket deltas. The Next.js engineering dashboard
> consumes those real contracts for live overview, charts, and catalog-driven signal inspection.
> Optional raw-CAN recording produces portable, hashed session artifacts that replay through the
> same DBC, telemetry engine, API, and dashboard. The Sessions page lists and starts those replays.
> A read-only Raw CAN Explorer observes the same pre-decode live or replay frames with a bounded
> buffer, DBC annotations, simulation-time rates, filters, and a dedicated raw WebSocket.
> A deterministic Python diagnostic engine evaluates coherent decoded telemetry, maintains five
> synthetic `TUN-*` DTC lifecycles with bounded events and immutable freeze frames, and exposes a
> REST-only Diagnostics workspace. Replay regenerates the same diagnostic state from raw frames.
> These definitions are not authentic BMW traffic. Database indexing, advanced playback controls,
> CAN transmission, fault injection, authentic OBD/UDS diagnostics, tuning, physical CAN,
> authentication, and simulator controls are not implemented.

## Architecture at a glance

The current data path is:

```text
live gateway or raw session -> RawCanFrame
                                  +-> SessionRecorder
                                  +-> CanExplorer -> raw REST/WebSocket -> CAN page
                                  +-> DBC -> TelemetryEngine -> telemetry REST/WebSocket -> dashboard
                                                           +-> DiagnosticEngine -> REST -> Diagnostics page
```

CAN is the required source-of-truth boundary for future frontend telemetry; the simulator will not
bypass the frame and decode pipeline. C++ owns lower-level simulation and frame publication. Python
begins at validated raw CAN and owns DBC decoding, telemetry aggregation, and the local service/API
boundary. TypeScript/Next.js owns observation-only presentation. PostgreSQL remains a future
persistence boundary.

## Repository layout

```text
backend/       Python gateway, raw sessions, DBC decoder, telemetry/diagnostic cores, and local API
can/           C++ Classic CAN, simulated DME/DSC publication, shared bus, and loopback gateway
frontend/      Next.js live engineering dashboard and telemetry client
shared/        Future language-neutral application contracts
simulator/     C++20 deterministic IDLE/COLD_START/WARMUP/CITY vehicle simulation
tests/python/  Python tests
tests/fixtures/Independent synthetic CAN golden vectors
docs/          Product and engineering specifications
.github/       Continuous integration
```

## Prerequisites

- Python 3.12 or newer
- CMake 3.25 or newer and a C++20 compiler (Visual Studio Build Tools on Windows)
- Node.js 20.9 or newer and npm
- Docker Desktop with Docker Compose

## Python setup and checks

From the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

## C++ build and tests

Run these commands in a shell where the Visual Studio C++ environment is available:

```powershell
cmake -S . -B build/cpp
cmake --build build/cpp --config Debug
ctest --test-dir build/cpp -C Debug --output-on-failure
```

Formatting is configured by `.clang-format`; when `clang-format` is installed, check it with:

```powershell
clang-format --dry-run --Werror (rg --files simulator can -g '*.hpp' -g '*.cpp')
```

## Live synthetic CAN gateway

After building Debug, start the unpaced, loopback-only C++ server in terminal 1:

```powershell
.\build\cpp\can\Debug\tuneros_gateway_sim.exe --scenario cold-start --port 45800
```

It prints `LISTENING 45800` and waits, preserving the initial frames. In terminal 2:

```powershell
.\.venv\Scripts\Activate.ps1
python -m tuneros.can.live_decode --port 45800
```

Supported scenarios are `idle`, `cold-start`, `warmup`, and `city`; `--step-us` and `--duration-us`
override run timing. The single-client server defaults to maximum speed, has no authentication or
TLS, and binds only `127.0.0.1`. This gateway carries raw synthetic CAN rather than decoded telemetry
and is not physical CAN.
The live output now includes synthetic DME messages `0x500–0x502` and simulated DSC motion/wheel
messages `0x520–0x521`; none are authentic BMW CAN definitions.

## Frontend setup and checks

```powershell
Set-Location frontend
npm install
npm run lint
npm run typecheck
npm test
npm run build
npm run dev
```

Use either `npm install` for dependency setup/update or `npm ci` for a clean lockfile install. Copy
`frontend/.env.example` to `frontend/.env.local` if the API is not on the documented local defaults.
The development server is available at `http://localhost:3000` by default. Overview and Telemetry
use one shared decoded WebSocket. `/can` mounts a separate page-scoped raw WebSocket and bounded CAN
inspection state. `/diagnostics` polls the small derived diagnostic REST surface. No page uses mock
telemetry or diagnostic data.

## Live telemetry API

After building C++, start a CITY gateway in terminal 1:

```powershell
.\build\cpp\can\Debug\tuneros_gateway_sim.exe --scenario city --port 45800
```

Start the local API in terminal 2:

```powershell
.\.venv\Scripts\Activate.ps1
python -m tuneros.api --gateway-port 45800 --port 8000
```

Open `http://127.0.0.1:8000/docs` for generated OpenAPI documentation. Status, catalog, and current
telemetry are available at `/api/v1/status`, `/api/v1/catalog`, and `/api/v1/telemetry`. The decoded
delta WebSocket is `/api/v1/ws/telemetry`. The service defaults to loopback and narrowly allows the
local frontend origins on port 3000; it has no authentication or TLS and is not a deployment
configuration. Because the simulator is intentionally unpaced, a six-second CITY run can arrive as
a burst; the dashboard consumes every latest-state update and retains its final state while sampling
chart points by simulation time.

## Raw CAN session recording and replay

Recording is opt-in. Start the gateway normally, then launch the API with a session name and optional
scenario metadata:

```powershell
python -m tuneros.api --gateway-port 45800 --record-session `
  --session-name "CITY baseline" --scenario city
```

Normal gateway EOF publishes a version-one `<uuid>.tuneros/` artifact under `data/sessions` by
default. Set `TUNEROS_SESSION_ROOT` or pass `--session-root` to change it. Replay needs no C++ process:

```powershell
python -m tuneros.api --replay-session <session-uuid>
```

Replay remains unpaced and begins after either telemetry or raw-CAN WebSocket initialization. It regenerates
decoded telemetry from the exact raw frames; no decoded snapshot is stored as canonical session
data. See [Session recording and replay](docs/SESSIONS.md).

## Raw CAN Explorer

Open `http://localhost:3000/can` during a live or replay source. The read-only page shows retained
raw frames, exact DLC/payload bytes, authoritative DBC annotations and decoded engineering values,
per-ID expected/observed rates, filters, and presentation-only Freeze View. The backend retains
4,096 frames; the browser retains 1,000 and renders at most 500. Unknown IDs and decode errors remain
visible as raw evidence. See [Raw CAN Explorer](docs/CAN_EXPLORER.md).

## Diagnostics

Open `http://localhost:3000/diagnostics` during a live or replay source. The page displays DTC
lifecycle counts, status-filtered records, selected rule detail, immutable first-activation freeze
frames, and the bounded transition timeline. Only historical DTCs can be cleared. Phase 7A defines
five conservative synthetic TunerOS rules; it does not claim BMW DTC fidelity, inject faults, send
diagnostic CAN traffic, or persist DTC records. See [Diagnostics](docs/DIAGNOSTICS.md).

## PostgreSQL

Create a local environment file, review its development-only values, then start PostgreSQL:

```powershell
Copy-Item .env.example .env
docker compose up -d
docker compose ps
```

Stop the service without deleting its named data volume:

```powershell
docker compose down
```

The `.env` file is ignored. Never commit real credentials. No application currently connects to the
database.

## Documentation

- [Product definition](docs/PRODUCT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Vehicle model specification](docs/VEHICLE_MODEL.md)
- [Simulation contracts](docs/SIMULATION_CONTRACTS.md)
- [CAN design](docs/CAN_DESIGN.md)
- [Raw CAN Explorer](docs/CAN_EXPLORER.md)
- [Telemetry contracts](docs/TELEMETRY.md)
- [Telemetry API](docs/API.md)
- [Frontend dashboard](docs/FRONTEND.md)
- [Session recording and replay](docs/SESSIONS.md)
- [Diagnostics direction](docs/DIAGNOSTICS.md)
- [Architecture decisions](docs/DECISIONS.md)
