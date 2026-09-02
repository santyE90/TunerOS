#include "tuneros/ecu/dme_frames.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace tuneros::ecu {
namespace {

[[nodiscard]] std::uint16_t encode_scaled_u16(double value, double scale, double offset) {
  if (!std::isfinite(value)) {
    throw std::invalid_argument("cannot encode a non-finite CAN signal");
  }
  const double raw = std::round((value - offset) / scale);
  return static_cast<std::uint16_t>(
      std::clamp(raw, 0.0, static_cast<double>(std::numeric_limits<std::uint16_t>::max())));
}

[[nodiscard]] std::uint8_t encode_scaled_u8(double value, double scale, double offset) {
  if (!std::isfinite(value)) {
    throw std::invalid_argument("cannot encode a non-finite CAN signal");
  }
  const double raw = std::round((value - offset) / scale);
  return static_cast<std::uint8_t>(
      std::clamp(raw, 0.0, static_cast<double>(std::numeric_limits<std::uint8_t>::max())));
}

[[nodiscard]] std::uint8_t encode_normalized_u8(double value) {
  return encode_scaled_u8(value, 1.0 / 255.0, 0.0);
}

void pack_u16_little_endian(std::array<std::uint8_t, 8>& payload, std::size_t offset,
                            std::uint16_t value) noexcept {
  payload[offset] = static_cast<std::uint8_t>(value & 0xFFU);
  payload[offset + 1] = static_cast<std::uint8_t>((value >> 8U) & 0xFFU);
}

}  // namespace

canbus::CanFrame make_dme_fast_engine_frame(const simulator::VehicleState& state) {
  canbus::CanFrame frame{
      .arbitration_id = kDmeFastEngineFrameId,
      .payload_length = kDmeFastEnginePayloadLength,
      .timestamp_microseconds = state.timestamp.microseconds,
  };
  pack_u16_little_endian(frame.payload, 0, encode_scaled_u16(state.engine_speed_rpm, 0.25, 0.0));
  frame.payload[2] = encode_normalized_u8(state.throttle_position);
  frame.payload[3] = encode_normalized_u8(state.engine_load);
  frame.payload[4] = state.engine_running ? 0x01U : 0x00U;
  return frame;
}

canbus::CanFrame make_dme_air_load_frame(const simulator::VehicleState& state) {
  canbus::CanFrame frame{
      .arbitration_id = kDmeAirLoadFrameId,
      .payload_length = kDmeAirLoadPayloadLength,
      .timestamp_microseconds = state.timestamp.microseconds,
  };
  pack_u16_little_endian(frame.payload, 0,
                         encode_scaled_u16(state.manifold_pressure_kpa_absolute, 0.1, 0.0));
  frame.payload[2] = encode_normalized_u8(state.accelerator_pedal_position);
  frame.payload[3] = encode_normalized_u8(state.requested_scenario_load);
  return frame;
}

canbus::CanFrame make_dme_thermal_electrical_frame(const simulator::VehicleState& state) {
  canbus::CanFrame frame{
      .arbitration_id = kDmeThermalElectricalFrameId,
      .payload_length = kDmeThermalElectricalPayloadLength,
      .timestamp_microseconds = state.timestamp.microseconds,
  };
  pack_u16_little_endian(frame.payload, 0,
                         encode_scaled_u16(state.coolant_temperature_celsius, 0.1, -100.0));
  pack_u16_little_endian(frame.payload, 2,
                         encode_scaled_u16(state.oil_temperature_celsius, 0.1, -100.0));
  pack_u16_little_endian(frame.payload, 4,
                         encode_scaled_u16(state.intake_air_temperature_celsius, 0.1, -100.0));
  frame.payload[6] = encode_scaled_u8(state.battery_voltage_volts, 0.1, 0.0);
  return frame;
}

}  // namespace tuneros::ecu
