#include "tuneros/simulator/initial_conditions.hpp"

#include <cmath>

#include "tuneros/simulator/model_parameters.hpp"

namespace tuneros::simulator {

bool is_valid(const SimulationInitialConditions& conditions,
              const VehicleProfile& profile) noexcept {
  const auto gear = static_cast<int>(conditions.current_gear);
  return is_valid(profile) && std::isfinite(conditions.engine_speed_rpm) &&
         conditions.engine_speed_rpm >= 0.0 && conditions.engine_speed_rpm <= profile.redline_rpm &&
         (conditions.engine_running || conditions.engine_speed_rpm == 0.0) &&
         std::isfinite(conditions.coolant_temperature_celsius) &&
         std::isfinite(conditions.oil_temperature_celsius) &&
         std::isfinite(conditions.intake_air_temperature_celsius) &&
         std::isfinite(conditions.battery_voltage_volts) &&
         conditions.battery_voltage_volts >= 0.0 &&
         std::isfinite(conditions.vehicle_speed_meters_per_second) &&
         conditions.vehicle_speed_meters_per_second >= 0.0 && gear >= 0 &&
         gear <= static_cast<int>(profile.forward_gear_count) &&
         (conditions.vehicle_speed_meters_per_second == 0.0 ||
          (conditions.engine_running && gear > 0));
}

SimulationInitialConditions make_idle_initial_conditions(
    const EnvironmentState& environment) noexcept {
  using namespace model_parameters;
  return {
      .engine_running = true,
      .engine_speed_rpm = kInitialEngineSpeedRpm,
      .coolant_temperature_celsius =
          environment.ambient_temperature_celsius + kInitialCoolantAboveAmbientCelsius,
      .oil_temperature_celsius =
          environment.ambient_temperature_celsius + kInitialOilAboveAmbientCelsius,
      .intake_air_temperature_celsius =
          environment.ambient_temperature_celsius + kInitialIntakeAirAboveAmbientCelsius,
      .battery_voltage_volts = kInitialBatteryVoltageVolts,
      .vehicle_speed_meters_per_second = 0.0,
      .current_gear = 0,
  };
}

SimulationInitialConditions make_cold_start_initial_conditions(
    const EnvironmentState& environment) noexcept {
  using namespace model_parameters;
  return {
      .engine_running = false,
      .engine_speed_rpm = 0.0,
      .coolant_temperature_celsius =
          environment.ambient_temperature_celsius + kColdStartCoolantAboveAmbientCelsius,
      .oil_temperature_celsius =
          environment.ambient_temperature_celsius + kColdStartOilAboveAmbientCelsius,
      .intake_air_temperature_celsius = environment.ambient_temperature_celsius,
      .battery_voltage_volts = kRestingBatteryVoltageVolts,
      .vehicle_speed_meters_per_second = 0.0,
      .current_gear = 0,
  };
}

SimulationInitialConditions make_warmup_initial_conditions(
    const EnvironmentState& environment) noexcept {
  using namespace model_parameters;
  return {
      .engine_running = true,
      .engine_speed_rpm = kIdleTargetRpm,
      .coolant_temperature_celsius =
          environment.ambient_temperature_celsius + kWarmupCoolantAboveAmbientCelsius,
      .oil_temperature_celsius =
          environment.ambient_temperature_celsius + kWarmupOilAboveAmbientCelsius,
      .intake_air_temperature_celsius =
          environment.ambient_temperature_celsius + kWarmupIntakeAirAboveAmbientCelsius,
      .battery_voltage_volts = kChargingVoltageVolts,
      .vehicle_speed_meters_per_second = 0.0,
      .current_gear = 0,
  };
}

SimulationInitialConditions make_city_initial_conditions(
    const EnvironmentState& environment) noexcept {
  using namespace model_parameters;
  return {
      .engine_running = true,
      .engine_speed_rpm = kIdleTargetRpm,
      .coolant_temperature_celsius =
          environment.ambient_temperature_celsius + kCityInitialCoolantAboveAmbientCelsius,
      .oil_temperature_celsius =
          environment.ambient_temperature_celsius + kCityInitialOilAboveAmbientCelsius,
      .intake_air_temperature_celsius =
          environment.ambient_temperature_celsius + kCityInitialIntakeAirAboveAmbientCelsius,
      .battery_voltage_volts = kChargingVoltageVolts,
      .vehicle_speed_meters_per_second = 0.0,
      .current_gear = 0,
  };
}

}  // namespace tuneros::simulator
