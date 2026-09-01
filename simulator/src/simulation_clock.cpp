#include "tuneros/simulator/simulation_clock.hpp"

#include <limits>
#include <stdexcept>

namespace tuneros::simulator {

SimulationClock::SimulationClock(SimulationDuration fixed_step) : fixed_step_(fixed_step) {
  if (fixed_step_.microseconds == 0) {
    throw std::invalid_argument("simulation fixed step must be positive");
  }
}

void SimulationClock::advance() { advance_ticks(1); }

void SimulationClock::advance_ticks(std::uint64_t count) {
  if (paused_ || count == 0) {
    return;
  }

  const auto maximum = std::numeric_limits<std::uint64_t>::max();
  if (count > (maximum - timestamp_.microseconds) / fixed_step_.microseconds) {
    throw std::overflow_error("simulation timestamp overflow");
  }

  timestamp_.microseconds += count * fixed_step_.microseconds;
  tick_count_ += count;
}

void SimulationClock::reset() noexcept {
  timestamp_ = {};
  tick_count_ = 0;
  paused_ = false;
}

}  // namespace tuneros::simulator
