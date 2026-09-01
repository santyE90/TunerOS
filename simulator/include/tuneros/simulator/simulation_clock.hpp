#pragma once

#include <cstdint>

#include "tuneros/simulator/contracts.hpp"

namespace tuneros::simulator {

class SimulationClock {
 public:
  explicit SimulationClock(SimulationDuration fixed_step = kBaseSimulationStep);

  [[nodiscard]] SimulationTimestamp timestamp() const noexcept { return timestamp_; }
  [[nodiscard]] SimulationDuration fixed_step() const noexcept { return fixed_step_; }
  [[nodiscard]] std::uint64_t tick_count() const noexcept { return tick_count_; }
  [[nodiscard]] bool is_paused() const noexcept { return paused_; }

  void advance();
  void advance_ticks(std::uint64_t count);
  void pause() noexcept { paused_ = true; }
  void resume() noexcept { paused_ = false; }
  void reset() noexcept;

 private:
  SimulationTimestamp timestamp_{};
  SimulationDuration fixed_step_;
  std::uint64_t tick_count_{};
  bool paused_{};
};

}  // namespace tuneros::simulator
