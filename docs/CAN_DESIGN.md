# CAN design

## Authenticity and source-of-truth rule

**Every identifier, cycle time, and signal layout through Phase 3A is a synthetic TunerOS simulation
definition. None is an authentic BMW CAN identifier, PT-CAN capture, reverse-engineered signal, or
OEM protocol definition.**

The vehicle simulation owns canonical `VehicleState`. Independent TunerOS simulated ECUs observe
selected state as read-only input, create raw binary frames, and share one CAN transport:

```text
VehicleState -> simulated DME + simulated DSC -> ordered binary CAN frames -> transport -> DBC
```

Production telemetry must consume the decoded CAN path. It must not read privileged `VehicleState`
directly. Tests may inspect both sides to verify the boundary.

Phase 6A's Raw CAN Explorer observes the existing `RawCanFrame` stream before decode. It does not
alter ECU publication, arbitration-ID order, transport, payload encoding, timestamping, or DBC
authority. Live gateway and session replay frames use the same explorer model. DBC-known frames gain
read-only metadata and engineering values; unknown IDs and decode failures remain visible raw
observations. The explorer cannot transmit or edit frames. See [Raw CAN Explorer](CAN_EXPLORER.md).

Vehicle speed remains absent from DME. Phase 3A makes the simulated DSC its synthetic CAN publisher.
The DSC derives four equal wheel speeds directly from vehicle speed because independent wheel physics
does not exist yet; `VehicleState` is not expanded with redundant wheel fields.

## Classic CAN frame contract

`tuneros::canbus::CanFrame` is an application-level Classic CAN data frame containing:

- unsigned 11-bit standard arbitration identifier, validated in `0x000..0x7FF`;
- payload length in `0..8` bytes;
- exactly eight bytes of payload storage, with DLC defining the meaningful prefix;
- unsigned 64-bit simulation timestamp in microseconds.

CAN FD, extended identifiers, remote/error frames, CRC, ACK, arbitration delay, bit timing, and the
physical layer are not modeled. Frame payload is opaque bytes—there are no named or floating-point
signals in `CanFrame`.

## Synthetic ECU identifier ranges and byte order

Phase 2A reserves standard-ID range `0x500..0x50F` for synthetic TunerOS DME publications. The three
implemented IDs are `0x500`, `0x501`, and `0x502`. Multi-byte signals use little-endian/Intel byte
order. Phase 3A reserves `0x520..0x52F` for simulated DSC publication and implements `0x520` and
`0x521`. These ranges and layouts are TunerOS-defined and not authentic BMW traffic.

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
| Vehicle motion | `0x520` | simulated DSC | 50 Hz | 3 | `VehicleSpeed` | `0.0` | 16 | no | 0.01 | 0 | m/s | 0..655.35 | `vehicle_speed_meters_per_second` |
| Vehicle motion | `0x520` | simulated DSC | 50 Hz | 3 | `CurrentGear` | `2.0` | 8 | no | 1 | 0 | gear | 0..6 | `current_gear` |
| Wheel speeds | `0x521` | simulated DSC | 50 Hz | 8 | `FrontLeftWheelSpeed` | `0.0` | 16 | no | 0.01 | 0 | m/s | 0..655.35 | derived from vehicle speed |
| Wheel speeds | `0x521` | simulated DSC | 50 Hz | 8 | `FrontRightWheelSpeed` | `2.0` | 16 | no | 0.01 | 0 | m/s | 0..655.35 | derived from vehicle speed |
| Wheel speeds | `0x521` | simulated DSC | 50 Hz | 8 | `RearLeftWheelSpeed` | `4.0` | 16 | no | 0.01 | 0 | m/s | 0..655.35 | derived from vehicle speed |
| Wheel speeds | `0x521` | simulated DSC | 50 Hz | 8 | `RearRightWheelSpeed` | `6.0` | 16 | no | 0.01 | 0 | m/s | 0..655.35 | derived from vehicle speed |

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

Phase 4A exposes transmitter, unit, signal, message, arbitration-ID, and cycle-time metadata through
immutable TunerOS-owned Python models. Telemetry consumers do not access `canmatrix` objects or
duplicate ID/source/unit/period tables. This metadata exposure does not change any DBC definition or
decode behavior.

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
  each signal resolution: 0.25 rpm, 1/255 normalized, 0.1 kPa, 0.1 degree Celsius, 0.1 V,
  0.01 m/s, or one gear.

`canmatrix` supplies DBC parsing and scaled decoding without requiring `python-can`. Phase 2C adds a
narrow standard-library TCP gateway but no FFI, physical adapter, queue, or telemetry service.

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

## Simulated DSC role and scheduling

`SimulatedDsc` is an observation/publication ECU. It contains no scenario IDs and does not mutate
vehicle state, apply brakes, request torque, implement ABS/traction/yaw control, or create faults and
diagnostics. `DscVehicleMotion` and `DscWheelSpeeds` both publish at 50 Hz, including an initial
snapshot at `t=0`. Their integer next-due timestamps use the same crossing, undersampling, overflow,
and reset semantics as DME.

Speed encoding is:

```text
raw_u16 = saturate(round(vehicle_speed_meters_per_second / 0.01), 0, 65535)
```

The raw value is little-endian. Finite out-of-range values saturate and non-finite values fail.
Current gear is an unsigned byte with neutral `0` and forward gears `1..6`. Each of the four wheel
signals independently receives the same encoded vehicle-speed value, so decoded wheel and vehicle
speeds agree exactly after quantization.

## Transport and integration

`CanTransport` currently defines synchronous `send(frame)`. `InMemoryTransport` validates frames
and stores them in deterministic FIFO insertion order. It provides empty/size/read-only queue
inspection, single-frame receive, full drain, and clear operations. It has no thread, socket,
latency, packet loss, arbitration simulator, or subscription system.

Both ECU APIs expose `collect_due_frames(state)`. The retained `observe_and_publish` convenience API
preserves standalone DME behavior, but combined publication uses `VehicleNetworkPublisher`: it
collects from DME and DSC, sorts the complete due set by ascending standard arbitration ID, then
sends through one transport. ECU call/registration order therefore cannot leak into bus order.

`VehicleNetworkSimulation` owns `VehicleSimulation`, `VehicleNetworkPublisher`, and an
`InMemoryTransport`. Construction publishes five initial frames in exact order `0x500`, `0x501`,
`0x502`, `0x520`, `0x521`. Reset restores vehicle and both schedulers, clears transport, and
republishes the same five frames. A default-step inclusive one-second run contains 163 DME frames,
102 DSC frames, and 265 combined frames.

The target dependency graph is acyclic:

```text
tuneros_can                 tuneros_simulator
     \                         /    \
      tuneros_dme      tuneros_dsc
              \         /
          tuneros_vehicle_network
```

SocketCAN, physical adapters, persistence, telemetry services, diagnostics, and UI integration
remain future work.

## Phase 2C TCP gateway protocol

The development gateway is a synchronous, one-client TCP server bound to `127.0.0.1`. Port `45800`
is the centralized default; port zero requests an OS-assigned ephemeral test port. The server accepts
a client before publishing time-zero frames. Simulation then runs unpaced and may block on local
socket writes; virtual simulation time and frame timestamps remain authoritative. There is no
authentication or TLS because exposure is loopback-only.

Phase 3A does not change this protocol or increment its version. Gateway records are generic
`CanFrame` envelopes, so the same version-one stream carries both DME and DSC IDs without
ECU-specific handling. `tuneros_gateway_sim` now uses `VehicleNetworkPublisher`, and the Python live
decoder recognizes DSC solely through the expanded authoritative DBC.

TCP carries one connection header followed by zero or more fixed 19-byte records. All envelope
integer metadata is unsigned network/big-endian. CAN payload bytes are copied unchanged; their
little-endian DBC signal encoding is a separate concern.

Connection header (8 bytes):

| Offset | Length | Field | Encoding | Description |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | Magic | ASCII | `TNCR` (`54 4E 43 52`) |
| 4 | 1 | Version | `uint8` | Protocol version `1` |
| 5 | 3 | Reserved | bytes | Must be zero |

CAN record (19 bytes):

| Offset | Length | Field | Encoding | Description |
| ---: | ---: | --- | --- | --- |
| 0 | 8 | Simulation timestamp | `uint64`, big-endian | Exact microseconds since reset |
| 8 | 2 | Arbitration ID | `uint16`, big-endian | Standard ID `0x000..0x7FF` |
| 10 | 1 | DLC | `uint8` | Meaningful payload length `0..8` |
| 11 | 8 | CAN payload slots | opaque bytes | First DLC bytes meaningful; remainder zero |

Version one has no negotiation. Python rejects bad magic, another version, nonzero reserved bytes,
invalid ID, or invalid DLC. Reads accumulate across arbitrary TCP segmentation, so split and
coalesced records have identical meaning. Stream order preserves the DME's `0x500`, `0x501`, `0x502`
ordering at equal timestamps. EOF between records is normal completion; EOF during a header or record
is truncation. Connection/write failure ends the run rather than silently dropping frames.

The independent golden vector is:

```text
header: 54 4E 43 52 01 00 00 00
frame:  timestamp=12,345,678, id=0x500, dlc=5, payload=70 17 80 40 01
record: 00 00 00 00 00 BC 61 4E 05 00 05 70 17 80 40 01 00 00 00
```

`TcpCanTransport` implements `CanTransport`, leaving `SimulatedDme` socket-agnostic:

```text
tuneros_can <- tuneros_can_gateway
tuneros_can + tuneros_simulator <- tuneros_dme
tuneros_can_gateway + tuneros_dme + tuneros_simulator <- tuneros_gateway_sim
```
