#pragma once

#include <array>
#include <optional>
#include <span>
#include <string_view>
#include <vector>

#include "tuneros/simulator/contracts.hpp"

namespace tuneros::simulator {

// Stable synthetic TunerOS fault identities. They are not BMW fault identifiers.
enum class FaultId {
  kCoolingSystemDegradation,
  kChargingSystemFailure,
  kMapSensorBias,
  kFrontLeftWheelSpeedSensorBias,
};

struct FaultConfiguration {
  FaultId id;
  SimulationTimestamp activation_time{};
  std::optional<SimulationTimestamp> deactivation_time{};

  friend constexpr bool operator==(const FaultConfiguration&, const FaultConfiguration&) = default;
};

using FaultConfigurations = std::vector<FaultConfiguration>;

// A compact evaluation result avoids repeated configuration scans during one simulation tick.
struct ActiveFaults {
  bool cooling_system_degradation{};
  bool charging_system_failure{};
  bool map_sensor_bias{};
  bool front_left_wheel_speed_sensor_bias{};

  friend constexpr bool operator==(const ActiveFaults&, const ActiveFaults&) = default;
};

// Physical truth remains in VehicleState. Only these ECU-facing observations may be sensor-biased.
struct SensorObservation {
  VehicleState dme_state;
  std::array<double, 4> wheel_speeds_meters_per_second{};

  friend constexpr bool operator==(const SensorObservation&, const SensorObservation&) = default;
};

namespace fault_parameters {

// Phase 7B synthetic assumptions; none are BMW specifications or calibration values.
inline constexpr double kDegradedCoolingEquilibriumCelsius = 140.0;
inline constexpr double kDegradedCoolingTimeConstantSeconds = 15.0;
inline constexpr double kFailedChargingVoltageVolts = 11.8;
inline constexpr double kFailedChargingTimeConstantSeconds = 0.5;
inline constexpr double kMapSensorBiasKpa = 220.0;
inline constexpr double kFrontLeftWheelSpeedSensorBiasMetersPerSecond = 5.0;

}  // namespace fault_parameters

[[nodiscard]] constexpr std::string_view fault_name(FaultId id) noexcept {
  switch (id) {
    case FaultId::kCoolingSystemDegradation:
      return "cooling-degradation";
    case FaultId::kChargingSystemFailure:
      return "charging-failure";
    case FaultId::kMapSensorBias:
      return "map-sensor-bias";
    case FaultId::kFrontLeftWheelSpeedSensorBias:
      return "front-left-wheel-speed-sensor-bias";
  }
  return "unknown";
}

[[nodiscard]] bool is_valid(const FaultConfiguration& configuration) noexcept;
[[nodiscard]] bool are_valid(std::span<const FaultConfiguration> configurations) noexcept;
[[nodiscard]] bool is_fault_active(const FaultConfiguration& configuration,
                                   SimulationTimestamp timestamp) noexcept;
[[nodiscard]] ActiveFaults active_faults_at(std::span<const FaultConfiguration> configurations,
                                            SimulationTimestamp timestamp) noexcept;
[[nodiscard]] SensorObservation observe_sensors(
    const VehicleState& state, std::span<const FaultConfiguration> configurations) noexcept;

}  // namespace tuneros::simulator
