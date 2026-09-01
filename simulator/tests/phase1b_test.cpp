#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string_view>

#include "tuneros/simulator/initial_conditions.hpp"
#include "tuneros/simulator/model_parameters.hpp"
#include "tuneros/simulator/scenario.hpp"
#include "tuneros/simulator/simulation.hpp"
#include "tuneros/simulator/vehicle_profiles.hpp"

namespace {

using namespace tuneros::simulator;

bool expect(bool condition, std::string_view message) {
  if (!condition) {
    std::cerr << message << '\n';
  }
  return condition;
}

bool nearly_equal(double left, double right, double tolerance = 1e-9) {
  return std::abs(left - right) <= tolerance;
}

bool test_initial_conditions_validation() {
  const auto profile = make_e90_335i_n54_manual_profile();
  const EnvironmentState environment{.ambient_temperature_celsius = -5.0,
                                     .ambient_pressure_kpa_absolute = 85.0};
  const auto cold = make_cold_start_initial_conditions(environment);
  if (!expect(is_valid(cold, profile) && !cold.engine_running && cold.engine_speed_rpm == 0.0,
              "Cold-start initial conditions must be valid, stopped, and at zero RPM")) {
    return false;
  }

  auto invalid = cold;
  invalid.engine_speed_rpm = 1.0;
  if (!expect(!is_valid(invalid, profile), "A stopped engine cannot have positive initial RPM")) {
    return false;
  }

  invalid = cold;
  invalid.coolant_temperature_celsius = std::numeric_limits<double>::quiet_NaN();
  if (!expect(!is_valid(invalid, profile), "Initial temperatures must be finite")) {
    return false;
  }

  invalid = cold;
  invalid.battery_voltage_volts = -1.0;
  if (!expect(!is_valid(invalid, profile), "Initial battery voltage cannot be negative")) {
    return false;
  }

  invalid = cold;
  invalid.vehicle_speed_meters_per_second = -0.1;
  if (!expect(!is_valid(invalid, profile), "Initial vehicle speed cannot be negative")) {
    return false;
  }

  invalid = cold;
  invalid.current_gear = 7;
  return expect(!is_valid(invalid, profile), "Initial gear must fit the selected profile");
}

bool test_environment_and_configurable_initial_state() {
  const EnvironmentState environment{.ambient_temperature_celsius = 10.0,
                                     .ambient_pressure_kpa_absolute = 90.0};
  const VehicleSimulation idle{make_default_idle_run_configuration(environment)};
  if (!expect(idle.state().coolant_temperature_celsius == 15.0 &&
                  idle.state().oil_temperature_celsius == 12.0 &&
                  idle.state().intake_air_temperature_celsius == 13.0,
              "Non-default ambient temperature must determine IDLE initial temperatures") ||
      !expect(idle.state().ambient_pressure_kpa_absolute == 90.0 &&
                  idle.state().manifold_pressure_kpa_absolute == 36.0,
              "Non-default ambient pressure must determine initial pressure state")) {
    return false;
  }

  const VehicleSimulation cold{make_default_cold_start_run_configuration(environment)};
  if (!expect(cold.state().coolant_temperature_celsius == 10.0 &&
                  cold.state().oil_temperature_celsius == 10.0 &&
                  cold.state().manifold_pressure_kpa_absolute == 90.0 &&
                  cold.state().actual_boost_kpa_gauge() == 0.0,
              "Engine-off cold start must begin at ambient temperature and pressure")) {
    return false;
  }

  auto configuration = make_default_warmup_run_configuration(environment);
  configuration.initial_conditions.engine_speed_rpm = 800.0;
  configuration.initial_conditions.coolant_temperature_celsius = 55.0;
  configuration.initial_conditions.oil_temperature_celsius = 45.0;
  configuration.initial_conditions.battery_voltage_volts = 13.9;
  VehicleSimulation warmup{configuration};
  const auto configured_initial_state = warmup.state();
  warmup.advance_ticks(100);
  warmup.reset();
  return expect(warmup.state() == configured_initial_state,
                "Reset must restore the exact explicitly configured initial state");
}

bool test_scenario_schedule_boundaries() {
  const EnvironmentState environment{};
  const auto before = scenario_inputs_for(
      ScenarioId::kColdStart,
      SimulationTimestamp{model_parameters::kColdStartRequestTimestampMicroseconds - 1},
      environment);
  const auto at_start = scenario_inputs_for(
      ScenarioId::kColdStart,
      SimulationTimestamp{model_parameters::kColdStartRequestTimestampMicroseconds}, environment);
  const auto halfway = scenario_inputs_for(
      ScenarioId::kColdStart,
      SimulationTimestamp{model_parameters::kColdStartRequestTimestampMicroseconds +
                          model_parameters::kColdStartStabilizationDurationMicroseconds / 2},
      environment);
  const auto stabilized = scenario_inputs_for(
      ScenarioId::kColdStart,
      SimulationTimestamp{model_parameters::kColdStartRequestTimestampMicroseconds +
                          model_parameters::kColdStartStabilizationDurationMicroseconds},
      environment);

  return expect(!before.engine_start_requested && before.requested_scenario_load == 0.0,
                "COLD_START inputs must remain pre-start before the exact request timestamp") &&
         expect(at_start.engine_start_requested &&
                    at_start.requested_scenario_load ==
                        model_parameters::kColdStartElevatedRequestedScenarioLoad,
                "COLD_START inputs must request start and elevated load at exactly one second") &&
         expect(nearly_equal(halfway.requested_scenario_load, 0.25),
                "COLD_START requested load must decay deterministically through stabilization") &&
         expect(nearly_equal(stabilized.requested_scenario_load,
                             model_parameters::kIdleRequestedScenarioLoad),
                "COLD_START requested load must reach normal IDLE at the exact phase boundary");
}

bool test_cold_start_and_reset_determinism() {
  const auto configuration = make_default_cold_start_run_configuration();
  VehicleSimulation first{configuration};
  VehicleSimulation second{configuration};
  const auto initial = first.state();

  if (!expect(!initial.engine_running && initial.engine_speed_rpm == 0.0 &&
                  initial.battery_voltage_volts == model_parameters::kRestingBatteryVoltageVolts &&
                  initial.vehicle_speed_meters_per_second == 0.0 && initial.current_gear == 0,
              "COLD_START must begin stopped, resting, stationary, and neutral")) {
    return false;
  }

  double peak_engine_speed{};
  const auto expected_ticks =
      configuration.duration.microseconds / configuration.fixed_step.microseconds;
  for (std::uint64_t tick = 1; tick <= expected_ticks; ++tick) {
    if (!expect(first.tick() && second.tick() && first.state() == second.state(),
                "Identical COLD_START runs must produce exactly equal state sequences")) {
      return false;
    }

    const auto& state = first.state();
    if (!expect(is_valid(state, configuration.vehicle_profile) &&
                    state.vehicle_speed_meters_per_second == 0.0 && state.current_gear == 0 &&
                    std::isfinite(state.actual_boost_kpa_gauge()),
                "Every COLD_START state must remain valid, stationary, and neutral")) {
      return false;
    }

    if (state.timestamp.microseconds < model_parameters::kColdStartRequestTimestampMicroseconds) {
      if (!expect(!state.engine_running && state.engine_speed_rpm == 0.0 &&
                      state.battery_voltage_volts == model_parameters::kRestingBatteryVoltageVolts,
                  "Pre-start state must remain exactly engine-off at resting voltage")) {
        return false;
      }
    } else if (state.timestamp.microseconds ==
               model_parameters::kColdStartRequestTimestampMicroseconds) {
      if (!expect(state.engine_running && state.engine_speed_rpm > 0.0,
                  "Engine start must occur at the exact deterministic request timestamp")) {
        return false;
      }
    }
    peak_engine_speed = std::max(peak_engine_speed, state.engine_speed_rpm);
  }

  const auto completed = first.state();
  if (!expect(peak_engine_speed > 900.0, "Cold-start RPM must rise above the normal idle region") ||
      !expect(completed.engine_speed_rpm >= 650.0 && completed.engine_speed_rpm <= 900.0,
              "Cold-start RPM must settle into the documented idle region") ||
      !expect(completed.battery_voltage_volts > initial.battery_voltage_volts &&
                  completed.battery_voltage_volts <= model_parameters::kChargingVoltageVolts,
              "Cold-start battery voltage must transition toward charging voltage") ||
      !expect(completed.coolant_temperature_celsius > initial.coolant_temperature_celsius &&
                  completed.oil_temperature_celsius > initial.oil_temperature_celsius,
              "Cold-start thermal state must warm after the engine starts")) {
    return false;
  }

  first.reset();
  if (!expect(first.state() == initial && first.clock().tick_count() == 0 &&
                  first.clock().timestamp().microseconds == 0,
              "COLD_START reset must exactly restore clock and initial state")) {
    return false;
  }
  first.run_to_completion();
  return expect(first.state() == completed,
                "A repeated COLD_START after reset must reproduce the exact final state");
}

bool test_warmup_long_run() {
  const auto configuration = make_default_warmup_run_configuration();
  VehicleSimulation first{configuration};
  VehicleSimulation second{configuration};
  const auto initial = first.state();
  const auto expected_ticks =
      configuration.duration.microseconds / configuration.fixed_step.microseconds;

  for (std::uint64_t tick = 0; tick < expected_ticks; ++tick) {
    if (!expect(first.tick() && second.tick() && first.state() == second.state(),
                "Identical WARMUP runs must produce exactly equal state sequences") ||
        !expect(is_valid(first.state(), configuration.vehicle_profile),
                "Every long-run WARMUP state must remain valid")) {
      return false;
    }
  }

  const auto& completed = first.state();
  return expect(completed.timestamp.microseconds == configuration.duration.microseconds &&
                    completed.run_state == SimulationRunState::kCompleted,
                "WARMUP must complete at its exact five-minute timestamp") &&
         expect(completed.engine_running && completed.vehicle_speed_meters_per_second == 0.0 &&
                    completed.current_gear == 0,
                "WARMUP must remain running, stationary, and neutral") &&
         expect(
             completed.coolant_temperature_celsius > initial.coolant_temperature_celsius &&
                 completed.coolant_temperature_celsius <
                     model_parameters::kCoolantIdleEquilibriumCelsius &&
                 completed.oil_temperature_celsius > initial.oil_temperature_celsius &&
                 completed.oil_temperature_celsius < model_parameters::kOilIdleEquilibriumCelsius,
             "Long-run WARMUP temperatures must remain bounded while approaching equilibrium");
}

bool test_cross_step_consistency() {
  auto cold_ten_configuration = make_default_cold_start_run_configuration();
  VehicleSimulation cold_ten{cold_ten_configuration};
  cold_ten.run_to_completion();

  auto cold_twenty_configuration = cold_ten_configuration;
  cold_twenty_configuration.fixed_step = SimulationDuration{20'000};
  VehicleSimulation cold_twenty{cold_twenty_configuration};
  cold_twenty.run_to_completion();

  const auto& cold_ten_state = cold_ten.state();
  const auto& cold_twenty_state = cold_twenty.state();
  if (!expect(
          nearly_equal(cold_ten_state.engine_speed_rpm, cold_twenty_state.engine_speed_rpm, 1e-6) &&
              nearly_equal(cold_ten_state.coolant_temperature_celsius,
                           cold_twenty_state.coolant_temperature_celsius, 0.01) &&
              nearly_equal(cold_ten_state.oil_temperature_celsius,
                           cold_twenty_state.oil_temperature_celsius, 0.01) &&
              nearly_equal(cold_ten_state.intake_air_temperature_celsius,
                           cold_twenty_state.intake_air_temperature_celsius, 0.01) &&
              nearly_equal(cold_ten_state.battery_voltage_volts,
                           cold_twenty_state.battery_voltage_volts, 1e-6),
          "COLD_START must remain physically consistent at 10 ms and 20 ms")) {
    return false;
  }

  auto warmup_ten_configuration = make_default_warmup_run_configuration();
  VehicleSimulation warmup_ten{warmup_ten_configuration};
  warmup_ten.run_to_completion();

  auto warmup_twenty_configuration = warmup_ten_configuration;
  warmup_twenty_configuration.fixed_step = SimulationDuration{20'000};
  VehicleSimulation warmup_twenty{warmup_twenty_configuration};
  warmup_twenty.run_to_completion();

  const auto& warmup_ten_state = warmup_ten.state();
  const auto& warmup_twenty_state = warmup_twenty.state();
  return expect(nearly_equal(warmup_ten_state.coolant_temperature_celsius,
                             warmup_twenty_state.coolant_temperature_celsius, 1e-8) &&
                    nearly_equal(warmup_ten_state.oil_temperature_celsius,
                                 warmup_twenty_state.oil_temperature_celsius, 1e-8),
                "WARMUP must remain tightly consistent at 10 ms and 20 ms");
}

bool test_cold_start_step_alignment() {
  auto configuration = make_default_cold_start_run_configuration();
  configuration.fixed_step = SimulationDuration{30'000};
  try {
    [[maybe_unused]] const VehicleSimulation simulation{configuration};
    return expect(false, "COLD_START must reject steps that cannot represent schedule boundaries");
  } catch (const std::invalid_argument&) {
    return true;
  }
}

bool test_still_unsupported_scenarios() {
  constexpr std::array unsupported{
      ScenarioId::kCity,     ScenarioId::kHighway,
      ScenarioId::kSpirited, ScenarioId::kWideOpenThrottlePull,
      ScenarioId::kDynoPull,
  };
  for (const auto scenario : unsupported) {
    auto configuration = make_default_idle_run_configuration();
    configuration.scenario = scenario;
    try {
      [[maybe_unused]] const VehicleSimulation simulation{configuration};
      return expect(false, "Post-Phase 1B unsupported scenarios must still fail clearly");
    } catch (const std::invalid_argument&) {
    }
  }
  return true;
}

}  // namespace

int main() {
  if (!test_initial_conditions_validation() || !test_environment_and_configurable_initial_state() ||
      !test_scenario_schedule_boundaries() || !test_cold_start_and_reset_determinism() ||
      !test_warmup_long_run() || !test_cross_step_consistency() ||
      !test_cold_start_step_alignment() || !test_still_unsupported_scenarios()) {
    return 1;
  }
  return 0;
}
