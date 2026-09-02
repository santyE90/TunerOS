# CAN workspace

Phase 2A implements the C++ application-level Classic CAN boundary here: canonical raw frames,
`CanTransport`, deterministic `InMemoryTransport`, synthetic DME frame packing/scheduling, and the
vehicle/network integration runner. The DME layouts and IDs are TunerOS synthetic definitions—not
authentic BMW traffic.

`tuneros_can` is independent of vehicle simulation. `tuneros_dme` depends on `tuneros_can` and
`tuneros_simulator`, leaving `VehicleSimulation` usable without a network. SocketCAN, physical
adapters, telemetry services, and persistence remain unimplemented.

Phase 2B adds the authoritative external DBC as packaged Python data under
`backend/src/tuneros/can/dbc/` and a Python decoder that begins at raw CAN rather than C++ vehicle
state. See [`docs/CAN_DESIGN.md`](../docs/CAN_DESIGN.md) for the authoritative layouts, scheduling,
and decode policies.

Phase 2C adds `tuneros_can_gateway`, a versioned fixed-record TCP loopback transport depending only
on generic CAN, plus `tuneros_gateway_sim`, which composes it with the simulator and DME. Python
receives this stream through the existing raw-frame boundary before DBC decode. The gateway is
single-client, blocking, unpaced, and local-development-only; it is not physical CAN or telemetry.

Phase 3A adds an independent observation-only simulated DSC, two synthetic motion publications, and
`VehicleNetworkPublisher`. DME and DSC collect due frames independently; the shared publisher sorts
the combined set by arbitration ID before sending it through one transport. Wheel speeds are derived
equally from canonical vehicle speed. No ABS, traction, braking, yaw control, faults, or diagnostics
are modeled, and the Phase 2C gateway protocol is unchanged.
