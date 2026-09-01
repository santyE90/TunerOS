# Architecture decisions

This file records accepted foundation decisions. Later changes should preserve the rationale or add
a dated superseding entry.

| Decision | Rationale |
| --- | --- |
| Use a monorepo | Cross-language contracts, tests, documentation, and CI evolve together. |
| Use a mixed-language architecture | Each language has a focused role without forcing one runtime onto every problem. |
| Use C++20 for authoritative vehicle-side contracts and simulation | It provides explicit data/control semantics and relevant systems experience; Python will not independently duplicate `VehicleState`. |
| Use Python 3.12+ for backend concerns | It supports rapid, testable work around telemetry, decoding, diagnostics, and APIs. |
| Use TypeScript and Next.js for the UI | They provide typed web contracts and a conventional React application boundary. |
| Start persistence with PostgreSQL | One general-purpose relational store is sufficient until measured needs justify more. |
| Use Docker Compose locally | It makes the required database reproducible without containerizing every developer tool. |
| Make CAN the telemetry source of truth | Vehicle state flows through ECU encoding and DBC decoding; direct simulator access is restricted to pre-CAN tests/tools. |
| Avoid a full physics engine | Learning goals require coherent signals and state transitions, not exhaustive dynamics. |
| Classify information as public reference, realistic simplification, or synthetic | Plausibility must never be mistaken for sourced BMW behavior. |
| Use deterministic fixed-step simulation independent of wall time | Runs and tests must be reproducible and able to execute faster or slower than real time. |
| Represent simulation time as unsigned integer microseconds | It is monotonic, excludes negative timestamps, supports planned rates, and avoids floating-point accumulation. |
| Start with a 10 ms / 100 Hz base tick | It is adequate for instructive engine-signal scheduling; slower work uses integer tick intervals. This is a TunerOS choice, not BMW timing. |
| Use SI-oriented canonical internal units and normalized `[0,1]` positions | Explicit boundary conversion prevents mixed-unit ambiguity; pressure names distinguish absolute and gauge values. |
| Keep configuration categories separate | Build, profile, run, calibration, and fault data have different owners and lifecycles. |
| Validate contract aggregates with explicit non-throwing helpers | Plain structs stay observable and easy to load; validation remains testable without hiding mutations in constructors. |
| Use exact first-order convergence for continuous state | `target + (current - target) * exp(-dt/tau)` is deterministic, bounded for positive steps, and consistent across reasonable fixed-step choices. The parameters are TunerOS assumptions. |
| Keep scenarios stateless and derived from simulation time | A scenario returns inputs for a scenario ID, integer timestamp, and environment. Reset therefore needs no hidden scenario-state cleanup, and schedule boundaries are directly testable. |
| Configure focused initial conditions instead of cloning VehicleState | Engine state/RPM, temperatures, voltage, speed, and gear materially affect current scenarios; remaining state is derived from profile, environment, scenario inputs, or model defaults. |
| Use synthetic direct speed-to-RPM factors for Phase 1C | Direct per-gear factors make gear/RPM relationships obvious without implying verified BMW ratios, tire dimensions, clutch behavior, or torque multiplication. |
| Treat CITY gear changes as scenario-controlled manual-driver choices | Speed thresholds select discrete gears for the six-speed manual reference profile. This is not an automatic transmission, EGS, or clutch simulation. |
| Use a minimal longitudinal response instead of force balance | Accelerator-derived drive acceleration minus synthetic rolling and speed-dependent loss produces bounded signals without torque curves, mass, tires, or wheel physics. |
| Avoid unnecessary distributed or units infrastructure | Message brokers, cloud services, and a dimensional-analysis library add no Phase 0 engineering value. |
| Defer application frameworks and schemas | FastAPI, ORMs, database migrations, and CAN libraries should follow concrete requirements. |
