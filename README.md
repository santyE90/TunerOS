# TunerOS

TunerOS is a BMW-focused automotive software engineering platform in its foundation phase. Its
long-term purpose is to make simulated vehicle behavior observable through the same boundaries an
automotive telemetry system would use: ECUs, binary CAN frames, decoded signals, backend services,
and a browser interface. The first reference vehicle will be a 2010 BMW E90 335i with the N54
engine.

> **Current status:** Phase 0A provides repository structure, toolchains, documentation, CI, and
> local PostgreSQL infrastructure only. Vehicle simulation, ECU behavior, CAN frames/DBC data,
> telemetry, diagnostics, tuning, and the product dashboard are not implemented.

## Architecture at a glance

The planned data path is:

```text
Vehicle model -> simulated ECUs -> binary CAN frames -> transport -> DBC decoder
              -> telemetry backend -> persistence / diagnostics / API -> frontend
```

CAN will be the source of truth for frontend telemetry; the simulator will not bypass the frame and
decode pipeline. C++ is reserved for lower-level simulation, Python for CAN/telemetry/diagnostics
services, TypeScript and Next.js for the UI, and PostgreSQL for durable data. These are boundaries,
not implemented product features in this phase.

## Repository layout

```text
backend/       Minimal importable Python package; future backend services
can/           Future CAN transport and DBC boundary
frontend/      Minimal Next.js and TypeScript application
shared/        Future language-neutral contracts and fixtures
simulator/     C++20 library and lightweight CTest
tests/python/  Python tests
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
clang-format --dry-run --Werror simulator/include/tuneros/simulator/version.hpp simulator/src/version.cpp simulator/tests/version_test.cpp
```

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
- [Vehicle model boundaries](docs/VEHICLE_MODEL.md)
- [CAN design](docs/CAN_DESIGN.md)
- [Diagnostics direction](docs/DIAGNOSTICS.md)
- [Architecture decisions](docs/DECISIONS.md)
