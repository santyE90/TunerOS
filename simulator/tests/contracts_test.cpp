#include "tuneros/simulator/contracts.hpp"

#include <cmath>
#include <iostream>
#include <limits>

namespace {

using tuneros::simulator::EnvironmentState;
using tuneros::simulator::InductionType;
using tuneros::simulator::is_valid;
using tuneros::simulator::kBaseSimulationStep;
using tuneros::simulator::TransmissionType;
using tuneros::simulator::VehicleProfile;
using tuneros::simulator::VehicleState;

static_assert(kBaseSimulationStep.microseconds == 10'000);

VehicleProfile reference_profile() {
  return {
      .profile_id = "bmw-e90-335i-n54-2010-manual",
      .manufacturer = "BMW",
      .model = "335i",
      .chassis = "E90",
      .model_year = 2010,
      .engine_family = "N54",
      .engine_identifier = "N54B30",
      .cylinder_count = 6,
      .displacement_liters = 2.979,
      .fuel_type = "gasoline",
      .induction_type = InductionType::kTwinTurbo,
      .transmission_type = TransmissionType::kManual,
      .forward_gear_count = 6,
      .redline_rpm = 7000.0,
      .baseline_calibration_id = "tuneros-n54-stock-baseline-v0",
  };
}

VehicleState valid_state() {
  return {
      .accelerator_pedal_position = 0.0,
      .requested_scenario_load = 0.0,
      .engine_running = true,
      .engine_speed_rpm = 700.0,
      .engine_load = 0.15,
      .throttle_position = 0.05,
      .vehicle_speed_meters_per_second = 0.0,
      .current_gear = 0,
      .ambient_pressure_kpa_absolute = 101.325,
      .manifold_pressure_kpa_absolute = 40.0,
      .requested_boost_kpa_gauge = 0.0,
      .coolant_temperature_celsius = 90.0,
      .oil_temperature_celsius = 95.0,
      .intake_air_temperature_celsius = 30.0,
      .lambda = 1.0,
      .ignition_advance_degrees = 8.0,
      .timing_correction_degrees = 0.0,
      .battery_voltage_volts = 14.0,
  };
}

}  // namespace

int main() {
  auto profile = reference_profile();
  if (!is_valid(profile)) {
    std::cerr << "Reference profile should satisfy its static contract\n";
    return 1;
  }

  auto invalid_profile = profile;
  invalid_profile.cylinder_count = 0;
  if (is_valid(invalid_profile)) {
    std::cerr << "A profile with no cylinders must be rejected\n";
    return 1;
  }

  const EnvironmentState default_environment;
  if (!is_valid(default_environment)) {
    std::cerr << "The documented local environment defaults must be valid\n";
    return 1;
  }

  auto state = valid_state();
  if (!is_valid(state, profile)) {
    std::cerr << "A state inside documented bounds should be valid\n";
    return 1;
  }

  if (std::abs(state.actual_boost_kpa_gauge() - (-61.325)) > 1e-9) {
    std::cerr << "Gauge boost must be derived from absolute manifold and ambient pressures\n";
    return 1;
  }

  state.accelerator_pedal_position = 1.01;
  if (is_valid(state, profile)) {
    std::cerr << "Normalized positions above one must be rejected\n";
    return 1;
  }

  state = valid_state();
  state.manifold_pressure_kpa_absolute = -1.0;
  if (is_valid(state, profile)) {
    std::cerr << "Negative absolute pressure must be rejected\n";
    return 1;
  }

  state = valid_state();
  state.coolant_temperature_celsius = std::numeric_limits<double>::quiet_NaN();
  if (is_valid(state, profile)) {
    std::cerr << "Non-finite temperatures must be rejected\n";
    return 1;
  }

  state = valid_state();
  state.engine_running = false;
  if (is_valid(state, profile)) {
    std::cerr << "An engine-off state must have exactly zero RPM\n";
    return 1;
  }

  return 0;
}
