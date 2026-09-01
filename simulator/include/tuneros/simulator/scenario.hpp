#pragma once

#include "tuneros/simulator/contracts.hpp"

namespace tuneros::simulator {

struct ScenarioInputs {
  double accelerator_pedal_position{};
  double requested_scenario_load{};
  bool command_vehicle_stationary{};
  bool engine_start_requested{};
  EnvironmentState environment{};

  friend constexpr bool operator==(const ScenarioInputs&, const ScenarioInputs&) = default;
};

[[nodiscard]] ScenarioInputs scenario_inputs_for(ScenarioId scenario, SimulationTimestamp timestamp,
                                                 const EnvironmentState& environment);

}  // namespace tuneros::simulator
