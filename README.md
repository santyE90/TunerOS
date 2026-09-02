# TunerOS

TunerOS is a BMW-focused automotive software engineering platform in its early simulation phase. Its
long-term purpose is to make simulated vehicle behavior observable through the same boundaries an
automotive telemetry system would use: ECUs, binary CAN frames, decoded signals, backend services,
and a browser interface. The first reference vehicle is a 2010 BMW E90 335i with the N54
engine.

> **Current status:** Phase 0, Phases 1A–1C, and Phases 2A–2C are complete. C++ provides
> deterministic vehicle simulation, simulated DME publication, synthetic binary Classic CAN, and
> in-memory transport. A versioned binary TCP loopback gateway carries those raw frames live into
> Python, which validates and decodes them through the packaged authoritative synthetic DBC. These
> definitions are not authentic BMW traffic. Physical CAN, telemetry services, persistence,
> diagnostics, tuning, WebSockets, and dashboard features are not implemented.

## Architecture at a glance

The planned data path is:

```text
Vehicle model -> simulated ECUs -> binary CAN frames -> transport -> DBC decoder
              -> telemetry backend -> persistence / diagnostics / API -> frontend
```

CAN is the required source-of-truth boundary for future frontend telemetry; the simulator will not
bypass the frame and decode pipeline. C++ owns lower-level simulation and frame publication. Python
begins at validated raw CAN and owns DBC decoding into engineering units. TypeScript/Next.js and
PostgreSQL remain future presentation and persistence boundaries.

## Repository layout

```text
backend/       Python raw-frame gateway client and DBC decoder; future backend services
can/           C++ Classic CAN, simulated DME publication, and loopback gateway
frontend/      Minimal Next.js and TypeScript application
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
TLS, and binds only `127.0.0.1`. This is a local process gateway, not physical CAN or telemetry.

## Frontend setup and checks

```powershell
Set-Location frontend
npm ci
npm run lint
npm run typecheck
npm run build
npm run dev
```

The development server is available at `http://localhost:3000` by default.

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
- [Diagnostics direction](docs/DIAGNOSTICS.md)
- [Architecture decisions](docs/DECISIONS.md)
