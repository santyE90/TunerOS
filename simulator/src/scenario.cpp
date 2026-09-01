#include "tuneros/simulator/scenario.hpp"

#include <algorithm>
#include <stdexcept>

#include "tuneros/simulator/model_parameters.hpp"

namespace tuneros::simulator {

ScenarioInputs scenario_inputs_for(ScenarioId scenario, SimulationTimestamp timestamp,
                                   const EnvironmentState& environment) {
  using namespace model_parameters;

  double requested_load = kIdleRequestedScenarioLoad;
  double accelerator = 0.0;
  bool stationary_intent = true;
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
    case ScenarioId::kCity:
      if (timestamp.microseconds < kCityFirstDepartureTimestampMicroseconds) {
        break;
      }
      stationary_intent = false;
      if (timestamp.microseconds < kCityFirstCruiseTimestampMicroseconds) {
        accelerator = kCityFirstAccelerationAccelerator;
        requested_load = kCityFirstAccelerationLoad;
      } else if (timestamp.microseconds < kCityFirstDecelerationTimestampMicroseconds) {
        accelerator = kCityFirstCruiseAccelerator;
        requested_load = kCityFirstCruiseLoad;
      } else if (timestamp.microseconds < kCityFirstStopIntentTimestampMicroseconds) {
        accelerator = 0.0;
      } else if (timestamp.microseconds < kCitySecondDepartureTimestampMicroseconds) {
        stationary_intent = true;
      } else if (timestamp.microseconds < kCitySecondCruiseTimestampMicroseconds) {
        accelerator = kCitySecondAccelerationAccelerator;
        requested_load = kCitySecondAccelerationLoad;
      } else if (timestamp.microseconds < kCityFinalDecelerationTimestampMicroseconds) {
        accelerator = kCitySecondCruiseAccelerator;
        requested_load = kCitySecondCruiseLoad;
      } else if (timestamp.microseconds < kCityFinalStopIntentTimestampMicroseconds) {
        accelerator = 0.0;
      } else {
        stationary_intent = true;
      }
      break;
    default:
      throw std::invalid_argument("scenario is not implemented in Phase 1C");
  }

  return {
      .accelerator_pedal_position = accelerator,
      .requested_scenario_load = requested_load,
      .command_vehicle_stationary = stationary_intent,
      .engine_start_requested = start_requested,
      .environment = environment,
  };
}

}  // namespace tuneros::simulator
