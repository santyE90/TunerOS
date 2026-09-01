# Architecture decisions

This file records accepted foundation decisions. Later changes should preserve the rationale or add a
dated superseding entry.

| Decision | Rationale |
| --- | --- |
| Use a monorepo | Cross-language contracts, tests, documentation, and CI evolve together. |
| Use a mixed-language architecture | Each language has a focused role without forcing one runtime onto every problem. |
| Use C++20 for lower-level simulation | It provides explicit data/control semantics and relevant systems experience. |
| Use Python 3.12+ for backend concerns | It supports rapid, testable work around telemetry, decoding, diagnostics, and APIs. |
| Use TypeScript and Next.js for the UI | They provide typed web contracts and a conventional React application boundary. |
| Start persistence with PostgreSQL | One general-purpose relational store is sufficient until measured needs justify more. |
| Use Docker Compose locally | It makes the required database reproducible without containerizing every developer tool. |
| Make CAN the telemetry source of truth | It keeps encoding, transport, decoding, and provenance visible end to end. |
| Avoid a full physics engine | The learning goals require coherent signals and state transitions, not exhaustive dynamics. |
| Label authentic, simplified, and fictional data | Plausibility must never be mistaken for sourced BMW behavior. |
| Avoid unnecessary distributed infrastructure | Redis, Kafka, MQTT, TimescaleDB, and cloud services add no Phase 0 value. |
| Defer application frameworks and schemas | FastAPI, ORMs, database migrations, and CAN libraries should follow concrete requirements. |
