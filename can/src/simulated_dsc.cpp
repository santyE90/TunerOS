#include "tuneros/ecu/simulated_dsc.hpp"

#include <stdexcept>

#include "periodic_publication.hpp"

namespace tuneros::ecu {

SimulatedDsc::SimulatedDsc(DscPublicationSchedule schedule) : schedule_(schedule) {
  if (schedule_.vehicle_motion_period_microseconds == 0 ||
      schedule_.wheel_speeds_period_microseconds == 0) {
    throw std::invalid_argument("DSC publication periods must be positive");
  }
}

std::vector<canbus::CanFrame> SimulatedDsc::collect_due_frames(
    const simulator::VehicleState& state) {
  return collect_due_frames(
      state, {state.vehicle_speed_meters_per_second, state.vehicle_speed_meters_per_second,
              state.vehicle_speed_meters_per_second, state.vehicle_speed_meters_per_second});
}

std::vector<canbus::CanFrame> SimulatedDsc::collect_due_frames(
    const simulator::VehicleState& state,
    const std::array<double, 4>& wheel_speeds_meters_per_second) {
  std::vector<canbus::CanFrame> frames;
  frames.reserve(2);
  const auto timestamp = state.timestamp.microseconds;

  if (timestamp >= next_vehicle_motion_timestamp_) {
    frames.push_back(make_dsc_vehicle_motion_frame(state));
    detail::advance_due_timestamp(next_vehicle_motion_timestamp_,
                                  schedule_.vehicle_motion_period_microseconds, timestamp);
  }
  if (timestamp >= next_wheel_speeds_timestamp_) {
    frames.push_back(make_dsc_wheel_speeds_frame(state, wheel_speeds_meters_per_second));
    detail::advance_due_timestamp(next_wheel_speeds_timestamp_,
                                  schedule_.wheel_speeds_period_microseconds, timestamp);
  }
  return frames;
}

void SimulatedDsc::observe_and_publish(const simulator::VehicleState& state,
                                       canbus::CanTransport& transport) {
  for (const auto& frame : collect_due_frames(state)) {
    transport.send(frame);
  }
}

void SimulatedDsc::reset() noexcept {
  next_vehicle_motion_timestamp_ = 0;
  next_wheel_speeds_timestamp_ = 0;
}

}  // namespace tuneros::ecu
