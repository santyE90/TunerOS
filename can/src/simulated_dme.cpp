#include "tuneros/ecu/simulated_dme.hpp"

#include <stdexcept>

#include "periodic_publication.hpp"

namespace tuneros::ecu {

SimulatedDme::SimulatedDme(DmePublicationSchedule schedule) : schedule_(schedule) {
  if (schedule_.fast_engine_period_microseconds == 0 ||
      schedule_.air_load_period_microseconds == 0 ||
      schedule_.thermal_electrical_period_microseconds == 0) {
    throw std::invalid_argument("DME publication periods must be positive");
  }
}

std::vector<canbus::CanFrame> SimulatedDme::collect_due_frames(
    const simulator::VehicleState& state) {
  std::vector<canbus::CanFrame> frames;
  frames.reserve(3);
  const auto timestamp = state.timestamp.microseconds;

  if (timestamp >= next_fast_engine_timestamp_) {
    frames.push_back(make_dme_fast_engine_frame(state));
    detail::advance_due_timestamp(next_fast_engine_timestamp_,
                                  schedule_.fast_engine_period_microseconds, timestamp);
  }
  if (timestamp >= next_air_load_timestamp_) {
    frames.push_back(make_dme_air_load_frame(state));
    detail::advance_due_timestamp(next_air_load_timestamp_, schedule_.air_load_period_microseconds,
                                  timestamp);
  }
  if (timestamp >= next_thermal_electrical_timestamp_) {
    frames.push_back(make_dme_thermal_electrical_frame(state));
    detail::advance_due_timestamp(next_thermal_electrical_timestamp_,
                                  schedule_.thermal_electrical_period_microseconds, timestamp);
  }
  return frames;
}

void SimulatedDme::observe_and_publish(const simulator::VehicleState& state,
                                       canbus::CanTransport& transport) {
  for (const auto& frame : collect_due_frames(state)) {
    transport.send(frame);
  }
}

void SimulatedDme::reset() noexcept {
  next_fast_engine_timestamp_ = 0;
  next_air_load_timestamp_ = 0;
  next_thermal_electrical_timestamp_ = 0;
}

}  // namespace tuneros::ecu
