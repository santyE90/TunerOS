#pragma once

#include "tuneros/simulator/contracts.hpp"

namespace tuneros::simulator {

struct SimulationInitialConditions {
  bool engine_running{};
  double engine_speed_rpm{};
  double coolant_temperature_celsius{};
  double oil_temperature_celsius{};
  double intake_air_temperature_celsius{};
  double battery_voltage_volts{};
  double vehicle_speed_meters_per_second{};
  std::int8_t current_gear{};

  friend constexpr bool operator==(const SimulationInitialConditions&,
                                   const SimulationInitialConditions&) = default;
};

[[nodiscard]] bool is_valid(const SimulationInitialConditions& conditions,
                            const VehicleProfile& profile) noexcept;

[[nodiscard]] SimulationInitialConditions make_idle_initial_conditions(
    const EnvironmentState& environment) noexcept;
[[nodiscard]] SimulationInitialConditions make_cold_start_initial_conditions(
    const EnvironmentState& environment) noexcept;
[[nodiscard]] SimulationInitialConditions make_warmup_initial_conditions(
    const EnvironmentState& environment) noexcept;

}  // namespace tuneros::simulator
