#include "tuneros/simulator/contracts.hpp"

#include <cmath>

namespace tuneros::simulator {
namespace {

[[nodiscard]] bool is_normalized(double value) noexcept {
  return std::isfinite(value) && value >= 0.0 && value <= 1.0;
}

}  // namespace

bool is_valid(const VehicleProfile& profile) noexcept {
  return !profile.profile_id.empty() && !profile.manufacturer.empty() && !profile.model.empty() &&
         !profile.chassis.empty() && profile.model_year > 0 && !profile.engine_family.empty() &&
         !profile.engine_identifier.empty() && profile.cylinder_count > 0 &&
         std::isfinite(profile.displacement_liters) && profile.displacement_liters > 0.0 &&
         !profile.fuel_type.empty() && profile.forward_gear_count >= 1 &&
         std::isfinite(profile.redline_rpm) && profile.redline_rpm > 0.0 &&
         !profile.baseline_calibration_id.empty();
}

bool is_valid(const EnvironmentState& environment) noexcept {
  return std::isfinite(environment.ambient_temperature_celsius) &&
         std::isfinite(environment.ambient_pressure_kpa_absolute) &&
         environment.ambient_pressure_kpa_absolute >= 0.0;
}

bool is_valid(const VehicleState& state, const VehicleProfile& profile) noexcept {
  const auto gear = static_cast<int>(state.current_gear);

  return is_valid(profile) && is_normalized(state.accelerator_pedal_position) &&
         is_normalized(state.requested_scenario_load) && std::isfinite(state.engine_speed_rpm) &&
         state.engine_speed_rpm >= 0.0 && state.engine_speed_rpm <= profile.redline_rpm &&
         (state.engine_running || state.engine_speed_rpm == 0.0) &&
         is_normalized(state.engine_load) && is_normalized(state.throttle_position) &&
         std::isfinite(state.vehicle_speed_meters_per_second) &&
         state.vehicle_speed_meters_per_second >= 0.0 && gear >= -1 &&
         gear <= static_cast<int>(profile.forward_gear_count) &&
         std::isfinite(state.ambient_pressure_kpa_absolute) &&
         state.ambient_pressure_kpa_absolute >= 0.0 &&
         std::isfinite(state.manifold_pressure_kpa_absolute) &&
         state.manifold_pressure_kpa_absolute >= 0.0 &&
         std::isfinite(state.requested_boost_kpa_gauge) &&
         std::isfinite(state.coolant_temperature_celsius) &&
         std::isfinite(state.oil_temperature_celsius) &&
         std::isfinite(state.intake_air_temperature_celsius) && std::isfinite(state.lambda) &&
         state.lambda > 0.0 && std::isfinite(state.ignition_advance_degrees) &&
         std::isfinite(state.timing_correction_degrees) && state.timing_correction_degrees <= 0.0 &&
         std::isfinite(state.battery_voltage_volts) && state.battery_voltage_volts >= 0.0;
}

}  // namespace tuneros::simulator
