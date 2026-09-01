#pragma once

#include "tuneros/simulator/contracts.hpp"

namespace tuneros::simulator {

struct ScenarioInput {
  double accelerator_pedal_position{};
  double requested_scenario_load{};
  bool command_vehicle_stationary{};
  EnvironmentState environment{};

  friend constexpr bool operator==(const ScenarioInput&, const ScenarioInput&) = default;
};

[[nodiscard]] ScenarioInput idle_scenario_input(SimulationTimestamp timestamp,
                                                const EnvironmentState& environment) noexcept;

}  // namespace tuneros::simulator
