#pragma once

#include <cstdint>

#include "tuneros/simulator/contracts.hpp"

namespace tuneros::simulator {

struct DrivetrainState {
  double vehicle_speed_meters_per_second{};
  std::int8_t selected_gear{};
  double engine_speed_rpm{};
};

[[nodiscard]] double engine_speed_for_gear(double vehicle_speed_meters_per_second, std::int8_t gear,
                                           const VehicleProfile& profile) noexcept;

[[nodiscard]] std::int8_t city_gear_for_speed(double vehicle_speed_meters_per_second,
                                              bool stationary_intent) noexcept;

[[nodiscard]] DrivetrainState evolve_city_drivetrain(double current_vehicle_speed_meters_per_second,
                                                     double accelerator_pedal_position,
                                                     bool stationary_intent,
                                                     double delta_time_seconds,
                                                     const VehicleProfile& profile) noexcept;

}  // namespace tuneros::simulator
