#include "tuneros/ecu/dme_frames.hpp"

#include "tuneros/ecu/detail/signal_encoding.hpp"

namespace tuneros::ecu {
canbus::CanFrame make_dme_fast_engine_frame(const simulator::VehicleState& state) {
  canbus::CanFrame frame{
      .arbitration_id = kDmeFastEngineFrameId,
      .payload_length = kDmeFastEnginePayloadLength,
      .timestamp_microseconds = state.timestamp.microseconds,
  };
  detail::pack_u16_little_endian(frame.payload, 0,
                                 detail::encode_scaled_u16(state.engine_speed_rpm, 0.25, 0.0));
  frame.payload[2] = detail::encode_normalized_u8(state.throttle_position);
  frame.payload[3] = detail::encode_normalized_u8(state.engine_load);
  frame.payload[4] = state.engine_running ? 0x01U : 0x00U;
  return frame;
}

canbus::CanFrame make_dme_air_load_frame(const simulator::VehicleState& state) {
  canbus::CanFrame frame{
      .arbitration_id = kDmeAirLoadFrameId,
      .payload_length = kDmeAirLoadPayloadLength,
      .timestamp_microseconds = state.timestamp.microseconds,
  };
  detail::pack_u16_little_endian(
      frame.payload, 0, detail::encode_scaled_u16(state.manifold_pressure_kpa_absolute, 0.1, 0.0));
  frame.payload[2] = detail::encode_normalized_u8(state.accelerator_pedal_position);
  frame.payload[3] = detail::encode_normalized_u8(state.requested_scenario_load);
  return frame;
}

canbus::CanFrame make_dme_thermal_electrical_frame(const simulator::VehicleState& state) {
  canbus::CanFrame frame{
      .arbitration_id = kDmeThermalElectricalFrameId,
      .payload_length = kDmeThermalElectricalPayloadLength,
      .timestamp_microseconds = state.timestamp.microseconds,
  };
  detail::pack_u16_little_endian(
      frame.payload, 0, detail::encode_scaled_u16(state.coolant_temperature_celsius, 0.1, -100.0));
  detail::pack_u16_little_endian(
      frame.payload, 2, detail::encode_scaled_u16(state.oil_temperature_celsius, 0.1, -100.0));
  detail::pack_u16_little_endian(
      frame.payload, 4,
      detail::encode_scaled_u16(state.intake_air_temperature_celsius, 0.1, -100.0));
  frame.payload[6] = detail::encode_scaled_u8(state.battery_voltage_volts, 0.1, 0.0);
  return frame;
}

}  // namespace tuneros::ecu
