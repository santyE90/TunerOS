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
  return make_dsc_wheel_speeds_frame(
      state, {state.vehicle_speed_meters_per_second, state.vehicle_speed_meters_per_second,
              state.vehicle_speed_meters_per_second, state.vehicle_speed_meters_per_second});
}

canbus::CanFrame make_dsc_wheel_speeds_frame(
    const simulator::VehicleState& state,
    const std::array<double, 4>& wheel_speeds_meters_per_second) {
  canbus::CanFrame frame{
      .arbitration_id = kDscWheelSpeedsFrameId,
      .payload_length = kDscWheelSpeedsPayloadLength,
      .timestamp_microseconds = state.timestamp.microseconds,
  };
  for (std::size_t index = 0; index < wheel_speeds_meters_per_second.size(); ++index) {
    detail::pack_u16_little_endian(frame.payload, index * 2,
                                   encode_speed(wheel_speeds_meters_per_second[index]));
  }
  return frame;
}

}  // namespace tuneros::ecu
