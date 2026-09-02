#include "tuneros/ecu/dsc_frames.hpp"

#include <algorithm>

#include "tuneros/ecu/detail/signal_encoding.hpp"

namespace tuneros::ecu {
namespace {

std::uint16_t encode_speed(double meters_per_second) {
  return detail::encode_scaled_u16(meters_per_second, kDscSpeedScaleMetersPerSecond, 0.0);
}

}  // namespace

canbus::CanFrame make_dsc_vehicle_motion_frame(const simulator::VehicleState& state) {
  canbus::CanFrame frame{
      .arbitration_id = kDscVehicleMotionFrameId,
      .payload_length = kDscVehicleMotionPayloadLength,
      .timestamp_microseconds = state.timestamp.microseconds,
  };
  detail::pack_u16_little_endian(frame.payload, 0,
                                 encode_speed(state.vehicle_speed_meters_per_second));
  frame.payload[2] = static_cast<std::uint8_t>(std::max(0, static_cast<int>(state.current_gear)));
  return frame;
}

canbus::CanFrame make_dsc_wheel_speeds_frame(const simulator::VehicleState& state) {
  canbus::CanFrame frame{
      .arbitration_id = kDscWheelSpeedsFrameId,
      .payload_length = kDscWheelSpeedsPayloadLength,
      .timestamp_microseconds = state.timestamp.microseconds,
  };
  const auto speed = encode_speed(state.vehicle_speed_meters_per_second);
  detail::pack_u16_little_endian(frame.payload, 0, speed);
  detail::pack_u16_little_endian(frame.payload, 2, speed);
  detail::pack_u16_little_endian(frame.payload, 4, speed);
  detail::pack_u16_little_endian(frame.payload, 6, speed);
  return frame;
}

}  // namespace tuneros::ecu
