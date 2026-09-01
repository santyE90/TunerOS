# CAN design

## Source-of-truth rule

CAN will eventually be the source of truth for vehicle telemetry. The vehicle simulation owns
canonical `VehicleState`; simulated ECUs observe selected state and own their controller state. ECU
publications then pass through binary frame transport and DBC decoding before becoming backend
signals or UI values:

```text
VehicleState -> ECU state -> binary CAN frame -> transport -> DBC decoder -> decoded signal
```

This preserves observable protocol boundaries and prevents telemetry, the backend, or the frontend
from depending on simulator internals. Until CAN exists, simulator tests/tools may inspect
`VehicleState` directly; that is explicitly not a production telemetry shortcut.

## Transport direction

A future transport abstraction will deal in timestamped opaque CAN frames and isolate send/receive
semantics from the underlying mechanism. Initial development must work well on Windows without
requiring a Linux-only kernel facility. Later adapters may support SocketCAN and physical CAN/OBD
hardware. No transport interface or hardware integration is implemented in Phase 1C.

## Authenticity disclaimer

Future CAN identifiers, payload layouts, cycle times, scaling, and DBC definitions created for
TunerOS are **simulated and fictional unless they are explicitly identified as sourced, with the
source and applicability documented**. Plausible values must not be described as authentic BMW CAN
data. Phase 1C defines no CAN identifiers or DBC content.
