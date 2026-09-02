# CAN workspace

Phase 2A implements the C++ application-level Classic CAN boundary here: canonical raw frames,
`CanTransport`, deterministic `InMemoryTransport`, synthetic DME frame packing/scheduling, and the
vehicle/network integration runner. The DME layouts and IDs are TunerOS synthetic definitions—not
authentic BMW traffic.

`tuneros_can` is independent of vehicle simulation. `tuneros_dme` depends on `tuneros_can` and
`tuneros_simulator`, leaving `VehicleSimulation` usable without a network. DBC decoding, Python CAN,
SocketCAN, physical adapters, telemetry, and persistence remain unimplemented.

Phase 2B adds the authoritative external DBC as packaged Python data under
`backend/src/tuneros/can/dbc/` and a Python decoder that begins at raw CAN rather than C++ vehicle
state. See [`docs/CAN_DESIGN.md`](../docs/CAN_DESIGN.md) for the authoritative layouts, scheduling,
and decode policies.
