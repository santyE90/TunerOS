# CAN design

## Authenticity and source-of-truth rule

**Every identifier, cycle time, and signal layout in Phases 2A–2B is a synthetic TunerOS simulation
definition. None is an authentic BMW CAN identifier, PT-CAN capture, reverse-engineered signal, or
OEM protocol definition.**

The vehicle simulation owns canonical `VehicleState`. The TunerOS simulated DME observes selected
state as read-only input, creates raw binary frames, and sends them through a CAN transport:

```text
VehicleState -> simulated DME -> binary CAN frame -> transport -> DBC decoder
```

Production telemetry must consume the decoded CAN path. It must not read privileged `VehicleState`
directly. Tests may inspect both sides to verify the boundary.

Vehicle speed is deliberately not DME-published. A future simulated DSC is the more coherent owner
for that publication. Phase 2A does not add DSC behavior.

## Classic CAN frame contract

`tuneros::canbus::CanFrame` is an application-level Classic CAN data frame containing:

- unsigned 11-bit standard arbitration identifier, validated in `0x000..0x7FF`;
- payload length in `0..8` bytes;
- exactly eight bytes of payload storage, with DLC defining the meaningful prefix;
- unsigned 64-bit simulation timestamp in microseconds.

CAN FD, extended identifiers, remote/error frames, CRC, ACK, arbitration delay, bit timing, and the
physical layer are not modeled. Frame payload is opaque bytes—there are no named or floating-point
signals in `CanFrame`.

## Synthetic DME identifier range and byte order

Phase 2A reserves standard-ID range `0x500..0x50F` for synthetic TunerOS DME publications. The three
implemented IDs are `0x500`, `0x501`, and `0x502`. Multi-byte signals use little-endian/Intel byte
order. The fixed layouts are described by the authoritative packaged DBC.

For all scaled signals:

```text
raw = round((physical_value - offset) / scale)
physical_value = raw * scale + offset
```

Finite values outside the raw type's representable range saturate to its nearest endpoint; they
never wrap or mask. Non-finite inputs are rejected. Normalized values saturate to `[0,1]` through
their effective `uint8` representation.

## Authoritative wire and DBC signal layouts

| Frame | Synthetic ID | Publisher | Rate | DLC | Signal | Byte.bit | Width | Signed | Scale | Offset | Unit | Representable range | `VehicleState` source |
| --- | --- | --- | ---: | ---: | --- | --- | ---: | --- | ---: | ---: | --- | --- | --- |
| Fast engine | `0x500` | simulated DME | 100 Hz | 5 | `EngineSpeedRpm` | `0.0` | 16 | no | 0.25 | 0 | rpm | 0..16,383.75 | `engine_speed_rpm` |
| Fast engine | `0x500` | simulated DME | 100 Hz | 5 | `ThrottlePosition` | `2.0` | 8 | no | 1/255 | 0 | normalized | 0..1 | `throttle_position` |
| Fast engine | `0x500` | simulated DME | 100 Hz | 5 | `EngineLoad` | `3.0` | 8 | no | 1/255 | 0 | normalized | 0..1 | `engine_load` |
| Fast engine | `0x500` | simulated DME | 100 Hz | 5 | `EngineRunning` | `4.0` | 1 | no | 1 | 0 | boolean | 0..1 | `engine_running` |
| Air/load | `0x501` | simulated DME | 50 Hz | 4 | `ManifoldPressureAbsolute` | `0.0` | 16 | no | 0.1 | 0 | kPa abs | 0..6,553.5 | `manifold_pressure_kpa_absolute` |
| Air/load | `0x501` | simulated DME | 50 Hz | 4 | `AcceleratorPedalPosition` | `2.0` | 8 | no | 1/255 | 0 | normalized | 0..1 | `accelerator_pedal_position` |
| Air/load | `0x501` | simulated DME | 50 Hz | 4 | `RequestedScenarioLoad` | `3.0` | 8 | no | 1/255 | 0 | normalized | 0..1 | `requested_scenario_load` |
| Thermal/electrical | `0x502` | simulated DME | 10 Hz | 7 | `CoolantTemperature` | `0.0` | 16 | no | 0.1 | -100 | degrees Celsius | -100..6,453.5 | `coolant_temperature_celsius` |
| Thermal/electrical | `0x502` | simulated DME | 10 Hz | 7 | `OilTemperature` | `2.0` | 16 | no | 0.1 | -100 | degrees Celsius | -100..6,453.5 | `oil_temperature_celsius` |
| Thermal/electrical | `0x502` | simulated DME | 10 Hz | 7 | `IntakeAirTemperature` | `4.0` | 16 | no | 0.1 | -100 | degrees Celsius | -100..6,453.5 | `intake_air_temperature_celsius` |
| Thermal/electrical | `0x502` | simulated DME | 10 Hz | 7 | `BatteryVoltage` | `6.0` | 8 | no | 0.1 | 0 | V | 0..25.5 | `battery_voltage_volts` |

Unused bits in the engine-running byte and bytes beyond DLC are zero in DME-generated frames.

## Authoritative DBC and Python decode contract

The external schema is packaged at
`backend/src/tuneros/can/dbc/tuneros_simulation.dbc`. It is a real DBC loaded through
`importlib.resources`, so decoding does not depend on the process working directory. The file itself
states that it is a TunerOS synthetic simulation database—not BMW, E90, N54, PT-CAN, captured, or
reverse-engineered OEM data.

The DBC is authoritative for downstream message names, signal names, bit positions, byte order,
signedness, scales, offsets, ranges, units, senders, and nominal cycle times. C++ retains the matching
constants necessary to produce bytes. Python does not repeat those layouts in production code;
contract tests compare DBC metadata and independently calculated wire vectors against the committed
C++ format.

`RawCanFrame` accepts one standard arbitration ID, `bytes` payload of up to eight bytes, and a
non-negative integer simulation timestamp. `TunerOsDbcDecoder` consumes only this raw contract and
returns `DecodedCanFrame` with ID, stable DBC message name, unchanged timestamp, and an immutable
mapping of engineering-unit values. `EngineRunning` is explicitly normalized to `bool`; remaining
signals are floats in their documented units.

Decode policies are deliberately strict:

- valid IDs absent from the DBC raise `UnknownCanFrameError` and are not called corrupt;
- known messages require their exact DBC DLC; both shorter and longer payloads raise
  `MalformedCanFrameError` rather than being padded, truncated, or partially decoded;
- raw timestamps are preserved exactly as unsigned-style integer microseconds, with no wall-clock or
  datetime conversion;
- decoded values are wire-quantized engineering values. Tests use tolerances of one millionth of
  each signal resolution: 0.25 rpm, 1/255 normalized, 0.1 kPa, 0.1 degree Celsius, or 0.1 V.

`canmatrix` supplies DBC parsing and scaled decoding without requiring the deferred `python-can`
transport package. No live C++/Python gateway, FFI, socket, pipe, or telemetry service exists in
Phase 2B.

## Simulated DME scheduling

The simulated DME contains publication state only; it does not own or mutate physical vehicle
state, recognize scenario IDs, simulate combustion, control throttle, or contain calibration or
diagnostic behavior.

All three frames publish an initial snapshot at `t=0`. Their next nominal due times are 10 ms,
20 ms, and 100 ms respectively. Each observed `VehicleState` is checked against integer next-due
timestamps. When a due time is reached or crossed:

- the frame uses the current observed state's timestamp and values;
- at most one instance of each frame type is emitted from that state;
- the next due timestamp advances by enough complete periods to lie in the future;
- simultaneous frames are emitted in ascending arbitration-ID order (`0x500`, `0x501`, `0x502`).

Therefore, non-divisible steps have bounded publication jitter of less than one simulation step and
do not interpolate state. Steps larger than a publication period intentionally undersample that
frame rather than duplicating one observed state. At the default 10 ms step, a run from `t=0`
through an inclusive one-second completion state produces 101 fast, 51 air/load, and 11
thermal/electrical frames.

## Transport and integration

`CanTransport` currently defines synchronous `send(frame)`. `InMemoryTransport` validates frames
and stores them in deterministic FIFO insertion order. It provides empty/size/read-only queue
inspection, single-frame receive, full drain, and clear operations. It has no thread, socket,
latency, packet loss, arbitration simulator, or subscription system.

`VehicleNetworkSimulation` is the small integration runner. It owns an independently usable
`VehicleSimulation`, a simulated DME, and an `InMemoryTransport`. Construction publishes the three
initial frames. Each successful vehicle tick exposes the resulting state to the DME. Reset restores
the vehicle, DME due timestamps, and empty transport, then republishes the same `t=0` snapshot.

The target dependency graph is acyclic:

```text
tuneros_can (frame + transport)       tuneros_simulator (VehicleState + evolution)
                   \                  /
                    tuneros_dme (DME frames, scheduler, integration runner)
```

SocketCAN, physical adapters, live Python CAN ingestion, persistence, telemetry, diagnostics, and UI
integration remain future work.
