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
| Make CAN the telemetry source of truth | Vehicle state flows through ECU encoding and DBC decoding; direct simulator access is restricted to simulator/encoding tests and tools. |
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
| Separate `tuneros_can`, `tuneros_simulator`, and `tuneros_dme` targets | Generic frame/transport code has no simulator dependency; DME integration depends on both, preserving an acyclic graph and standalone vehicle simulation. |
| Use synthetic standard-ID DME frames in reserved range `0x500..0x50F` | Fixed 11-bit IDs, byte-aligned little-endian layouts, and explicit scaling create a clear future DBC contract without implying BMW authenticity. |
| Publish initial ECU snapshots at simulation time zero | Consumers receive a deterministic initial state; inclusive run-end publication makes counts and replay behavior explicit. |
| Schedule DME frames with integer next-due timestamps | Timestamp crossing supports non-divisible simulation steps without wall time or interpolation; at most one frame type per observed state avoids duplicate samples. |
| Order simultaneous frames by ascending arbitration ID | It is deterministic and resembles CAN priority ordering without simulating arbitration delay. |
| Make the packaged DBC the authoritative external signal schema | C++ retains encoder constants to produce the wire format; downstream engineering meaning comes from one DBC rather than a duplicate Python layout table. |
| Begin Python at a validated raw-CAN boundary | `RawCanFrame` carries only ID, bytes, and simulation timestamp, preventing Python/backend code from accessing privileged `VehicleState`. |
| Use `canmatrix` for Phase 2B DBC parsing | It loads and decodes a real DBC without requiring the explicitly deferred `python-can` transport dependency; `cantools` was evaluated but currently requires `python-can`. |
| Defer live C++/Python transport bridging through Phase 2B | Golden raw-frame vectors first proved the cross-language contract without prematurely coupling runtimes; Phase 2C supersedes this deferral. |
| Use TCP loopback for the Phase 2C development gateway | It is language-neutral, native on Windows/POSIX, broker-free, and supported by standard libraries. Loopback binding limits unauthenticated and unencrypted exposure. |
| Use a versioned header plus fixed binary gateway records | `TNCR` version 1 and 19-byte records handle arbitrary TCP segmentation without JSON, native struct layout, or per-frame magic. |
| Keep raw CAN as the live process boundary | C++ sends ID, DLC/payload, and authoritative simulation time; Python constructs the existing `RawCanFrame` and uses the unchanged DBC decoder. |
| Keep the Phase 2C gateway synchronous and unpaced | One client and blocking writes provide a small lossless bridge; wall time, reconnect/replay, multi-client buffering, and brokers add no current value. |
| Make simulated DSC the synthetic vehicle/wheel-speed publisher | Vehicle speed was intentionally omitted from DME; DSC provides a coherent observation/publication boundary without stability-control algorithms. |
| Derive four equal wheel speeds without adding `VehicleState` fields | Phase 3A has no independent wheel physics, so storing four redundant values would create unnecessary state and reset obligations. |
| Collect ECU frames before shared-bus publication | DME and DSC independently return due frames; `VehicleNetworkPublisher` sorts the combined set by ascending arbitration ID, preventing call order from defining bus order. |
| Use synthetic DSC range `0x520..0x52F` | It is distinct from synthetic DME range `0x500..0x50F`; current `0x520` and `0x521` layouts are TunerOS-defined, not BMW traffic. |
| Begin telemetry at `DecodedCanFrame` | The telemetry domain receives authoritative decoded engineering observations and never reaches around CAN/DBC to `VehicleState` or simulator objects. |
| Wrap DBC metadata in immutable TunerOS models | Transmitter, unit, and cycle time remain authoritative without exposing `canmatrix` as an application-domain dependency. |
| Key telemetry by message and signal name | `SignalKey(message_name, signal_name)` remains semantic and unique if different ECUs later publish identically named signals; CAN ID remains provenance. |
| Reject backward live telemetry timestamps | Equal simulation timestamps and duplicates preserve bus arrival order, while older frames fail explicitly instead of being silently sorted. |
| Bound history by per-engine sample count | A default capacity of 256 keeps memory finite while retaining every update until oldest-first eviction; no resampling occurs. |
| Define freshness as at most two DBC periods old | Simulation time and authoritative DBC cycle time provide deterministic fresh/stale semantics without wall clocks or diagnostic quality scores. |
| Keep Phase 4A in memory and non-derived | Resettable latest state, histories, snapshots, and statistics establish the domain contract; persistence and vehicle-level derived signals remain future concerns. |
| Avoid unnecessary distributed or units infrastructure | Message brokers, cloud services, and a dimensional-analysis library add no Phase 0 engineering value. |
| Defer application frameworks and schemas | FastAPI, ORMs, database migrations, and CAN libraries should follow concrete requirements. |
