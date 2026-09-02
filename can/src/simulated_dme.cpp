#include "tuneros/ecu/simulated_dme.hpp"

#include <limits>
#include <stdexcept>

namespace tuneros::ecu {
namespace {

void advance_due_timestamp(std::uint64_t& next_due, std::uint64_t period,
                           std::uint64_t observed_timestamp) noexcept {
  const std::uint64_t periods_to_advance = (observed_timestamp - next_due) / period + 1;
  const std::uint64_t maximum_increment = std::numeric_limits<std::uint64_t>::max() - next_due;
  if (periods_to_advance > maximum_increment / period) {
    next_due = std::numeric_limits<std::uint64_t>::max();
    return;
  }
  next_due += periods_to_advance * period;
}

}  // namespace

SimulatedDme::SimulatedDme(DmePublicationSchedule schedule) : schedule_(schedule) {
  if (schedule_.fast_engine_period_microseconds == 0 ||
      schedule_.air_load_period_microseconds == 0 ||
      schedule_.thermal_electrical_period_microseconds == 0) {
    throw std::invalid_argument("DME publication periods must be positive");
  }
}

void SimulatedDme::observe_and_publish(const simulator::VehicleState& state,
                                       canbus::CanTransport& transport) {
  const auto timestamp = state.timestamp.microseconds;

  // Synthetic IDs ascend by publication group, defining deterministic same-timestamp ordering.
  if (timestamp >= next_fast_engine_timestamp_) {
    transport.send(make_dme_fast_engine_frame(state));
    advance_due_timestamp(next_fast_engine_timestamp_, schedule_.fast_engine_period_microseconds,
                          timestamp);
  }
  if (timestamp >= next_air_load_timestamp_) {
    transport.send(make_dme_air_load_frame(state));
    advance_due_timestamp(next_air_load_timestamp_, schedule_.air_load_period_microseconds,
                          timestamp);
  }
  if (timestamp >= next_thermal_electrical_timestamp_) {
    transport.send(make_dme_thermal_electrical_frame(state));
    advance_due_timestamp(next_thermal_electrical_timestamp_,
                          schedule_.thermal_electrical_period_microseconds, timestamp);
  }
}

void SimulatedDme::reset() noexcept {
  next_fast_engine_timestamp_ = 0;
  next_air_load_timestamp_ = 0;
  next_thermal_electrical_timestamp_ = 0;
}

}  // namespace tuneros::ecu
