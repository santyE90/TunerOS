#include "tuneros/simulator/scenario.hpp"

#include <algorithm>
#include <stdexcept>

#include "tuneros/simulator/model_parameters.hpp"

namespace tuneros::simulator {

ScenarioInputs scenario_inputs_for(ScenarioId scenario, SimulationTimestamp timestamp,
                                   const EnvironmentState& environment) {
  using namespace model_parameters;

  double requested_load = kIdleRequestedScenarioLoad;
  bool start_requested = false;

  switch (scenario) {
    case ScenarioId::kIdle:
    case ScenarioId::kWarmup:
      break;
    case ScenarioId::kColdStart: {
      if (timestamp.microseconds < kColdStartRequestTimestampMicroseconds) {
        requested_load = 0.0;
        break;
      }

      start_requested = true;
      const auto elapsed_since_start =
          timestamp.microseconds - kColdStartRequestTimestampMicroseconds;
      const double elevated_fraction =
          1.0 - std::min(1.0, static_cast<double>(elapsed_since_start) /
                                  static_cast<double>(kColdStartStabilizationDurationMicroseconds));
      requested_load = kIdleRequestedScenarioLoad +
                       (kColdStartElevatedRequestedScenarioLoad - kIdleRequestedScenarioLoad) *
                           elevated_fraction;
      break;
    }
    default:
      throw std::invalid_argument("scenario is not implemented in Phase 1B");
  }

  return {
      .accelerator_pedal_position = 0.0,
      .requested_scenario_load = requested_load,
      .command_vehicle_stationary = true,
      .engine_start_requested = start_requested,
      .environment = environment,
  };
}

}  // namespace tuneros::simulator
