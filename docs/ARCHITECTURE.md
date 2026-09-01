# Architecture

## Intended data flow

```text
Vehicle Model
  -> simulated ECUs
  -> binary CAN frames
  -> CAN transport
  -> DBC decoder
  -> telemetry backend
  -> persistence / diagnostics / API
  -> frontend
```

The decoded API is downstream of CAN. The vehicle model must not feed decoded values directly to the
frontend, because doing so would hide the protocol and decoding boundaries the project is meant to
teach.

## Responsibilities

- **C++**: deterministic vehicle state and simulated ECU behavior where lower-level control and
  timing are instructive.
- **Python**: CAN adapters, decoding orchestration, telemetry ingestion, rules-based diagnostics,
  persistence integration, and HTTP/WebSocket services.
- **TypeScript/Next.js**: operator-facing visualization and investigation workflows.
- **PostgreSQL**: durable configuration, session, decoded telemetry, diagnostic, and analysis data
  when those models are introduced.
- **Docker Compose**: reproducible local infrastructure, currently PostgreSQL only.

## Separation of concerns

Simulation owns state evolution; ECUs own emitted messages; transports move opaque frames; DBC
decoding assigns signal meaning; the backend owns application workflows; and the frontend consumes
backend contracts. Language-neutral contracts belong in `shared/` only once real consumers exist.

## Transport abstraction

A future CAN transport interface will separate producers/consumers from the mechanism carrying a
frame. The first implementation can be an in-process or Windows-friendly virtual transport. Later
adapters may target SocketCAN or physical CAN hardware without changing the simulator, decoder, or
application layers. The interface is intentionally not designed in Phase 0A.

## Phase 0A versus the future system

Phase 0A contains buildable package shells, a minimal UI, PostgreSQL configuration, CI, and written
boundaries. It contains no vehicle model, ECU, frame, DBC, transport, telemetry service, database
schema, diagnostics engine, or frontend product feature. Those arrive incrementally in later phases.

