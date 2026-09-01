#include "tuneros/simulator/scenario.hpp"

#include "tuneros/simulator/model_parameters.hpp"

namespace tuneros::simulator {

ScenarioInput idle_scenario_input([[maybe_unused]] SimulationTimestamp timestamp,
                                  const EnvironmentState& environment) noexcept {
  return {
      .accelerator_pedal_position = 0.0,
      .requested_scenario_load = model_parameters::kIdleRequestedScenarioLoad,
      .command_vehicle_stationary = true,
      .environment = environment,
  };
}

}  // namespace tuneros::simulator
