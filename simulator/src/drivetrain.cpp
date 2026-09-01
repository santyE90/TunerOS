#include "tuneros/simulator/drivetrain.hpp"

#include <algorithm>

#include "tuneros/simulator/model_parameters.hpp"

namespace tuneros::simulator {
namespace {

[[nodiscard]] double rpm_factor_for_gear(std::int8_t gear) noexcept {
  using namespace model_parameters;
  switch (gear) {
    case 1:
      return kGear1RpmPerMeterPerSecond;
    case 2:
      return kGear2RpmPerMeterPerSecond;
    case 3:
      return kGear3RpmPerMeterPerSecond;
    case 4:
      return kGear4RpmPerMeterPerSecond;
    case 5:
      return kGear5RpmPerMeterPerSecond;
    case 6:
      return kGear6RpmPerMeterPerSecond;
    default:
      return 0.0;
  }
}

}  // namespace

double engine_speed_for_gear(double vehicle_speed_meters_per_second, std::int8_t gear,
                             const VehicleProfile& profile) noexcept {
  if (gear <= 0 || vehicle_speed_meters_per_second <= 0.0) {
    return model_parameters::kIdleTargetRpm;
  }

  const double coupled_rpm = vehicle_speed_meters_per_second * rpm_factor_for_gear(gear);
  return std::clamp(coupled_rpm, model_parameters::kIdleTargetRpm, profile.redline_rpm);
}

std::int8_t city_gear_for_speed(double vehicle_speed_meters_per_second,
                                bool stationary_intent) noexcept {
  using namespace model_parameters;
  if (stationary_intent &&
      vehicle_speed_meters_per_second <= kCityStopSpeedEpsilonMetersPerSecond) {
    return 0;
  }
  if (vehicle_speed_meters_per_second < kCitySecondGearThresholdMetersPerSecond) {
    return 1;
  }
  if (vehicle_speed_meters_per_second < kCityThirdGearThresholdMetersPerSecond) {
    return 2;
  }
  if (vehicle_speed_meters_per_second < kCityFourthGearThresholdMetersPerSecond) {
    return 3;
  }
  return 4;
}

DrivetrainState evolve_city_drivetrain(double current_vehicle_speed_meters_per_second,
                                       double accelerator_pedal_position, bool stationary_intent,
                                       double delta_time_seconds,
                                       const VehicleProfile& profile) noexcept {
  using namespace model_parameters;

  double acceleration{};
  if (stationary_intent) {
    acceleration = current_vehicle_speed_meters_per_second > 0.0
                       ? -kCityStopDecelerationMetersPerSecondSquared
                       : 0.0;
  } else {
    const double drive_acceleration =
        accelerator_pedal_position * kCityMaximumDriveAccelerationMetersPerSecondSquared;
    const double resistance =
        current_vehicle_speed_meters_per_second > 0.0
            ? kCityRollingDecelerationMetersPerSecondSquared +
                  kCityDragDecelerationPerMeterPerSecond * current_vehicle_speed_meters_per_second
            : 0.0;
    acceleration = drive_acceleration - resistance;
  }

  double speed =
      std::max(0.0, current_vehicle_speed_meters_per_second + acceleration * delta_time_seconds);
  if (stationary_intent && speed <= kCityStopSpeedEpsilonMetersPerSecond) {
    speed = 0.0;
  }

  const auto gear = city_gear_for_speed(speed, stationary_intent);
  return {
      .vehicle_speed_meters_per_second = speed,
      .selected_gear = gear,
      .engine_speed_rpm = engine_speed_for_gear(speed, gear, profile),
  };
}

}  // namespace tuneros::simulator
