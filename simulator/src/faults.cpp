#include "tuneros/simulator/faults.hpp"

#include <algorithm>

namespace tuneros::simulator {

bool is_valid(const FaultConfiguration& configuration) noexcept {
  const bool known_id = [&configuration] {
    switch (configuration.id) {
      case FaultId::kCoolingSystemDegradation:
      case FaultId::kChargingSystemFailure:
      case FaultId::kMapSensorBias:
      case FaultId::kFrontLeftWheelSpeedSensorBias:
        return true;
    }
    return false;
  }();
  return known_id && (!configuration.deactivation_time.has_value() ||
                      configuration.deactivation_time->microseconds >
                          configuration.activation_time.microseconds);
}

bool are_valid(std::span<const FaultConfiguration> configurations) noexcept {
  for (std::size_t index = 0; index < configurations.size(); ++index) {
    if (!is_valid(configurations[index])) {
      return false;
    }
    for (std::size_t other = index + 1; other < configurations.size(); ++other) {
      if (configurations[index].id == configurations[other].id) {
        return false;
      }
    }
  }
  return true;
}

bool is_fault_active(const FaultConfiguration& configuration,
                     SimulationTimestamp timestamp) noexcept {
  return timestamp.microseconds >= configuration.activation_time.microseconds &&
         (!configuration.deactivation_time.has_value() ||
          timestamp.microseconds < configuration.deactivation_time->microseconds);
}

ActiveFaults active_faults_at(std::span<const FaultConfiguration> configurations,
                              SimulationTimestamp timestamp) noexcept {
  ActiveFaults result;
  for (const auto& configuration : configurations) {
    if (!is_fault_active(configuration, timestamp)) {
      continue;
    }
    switch (configuration.id) {
      case FaultId::kCoolingSystemDegradation:
        result.cooling_system_degradation = true;
        break;
      case FaultId::kChargingSystemFailure:
        result.charging_system_failure = true;
        break;
      case FaultId::kMapSensorBias:
        result.map_sensor_bias = true;
        break;
      case FaultId::kFrontLeftWheelSpeedSensorBias:
        result.front_left_wheel_speed_sensor_bias = true;
        break;
    }
  }
  return result;
}

SensorObservation observe_sensors(const VehicleState& state,
                                  std::span<const FaultConfiguration> configurations) noexcept {
  SensorObservation observation{
      .dme_state = state,
      .wheel_speeds_meters_per_second =
          {
              state.vehicle_speed_meters_per_second,
              state.vehicle_speed_meters_per_second,
              state.vehicle_speed_meters_per_second,
              state.vehicle_speed_meters_per_second,
          },
  };
  const auto active = active_faults_at(configurations, state.timestamp);
  if (active.map_sensor_bias) {
    observation.dme_state.manifold_pressure_kpa_absolute =
        std::max(0.0, state.manifold_pressure_kpa_absolute + fault_parameters::kMapSensorBiasKpa);
  }
  if (active.front_left_wheel_speed_sensor_bias) {
    observation.wheel_speeds_meters_per_second[0] =
        std::max(0.0, state.vehicle_speed_meters_per_second +
                          fault_parameters::kFrontLeftWheelSpeedSensorBiasMetersPerSecond);
  }
  return observation;
}

}  // namespace tuneros::simulator
