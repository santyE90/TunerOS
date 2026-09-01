#include "tuneros/simulator/simulation.hpp"

#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string_view>

#include "tuneros/simulator/model_parameters.hpp"
#include "tuneros/simulator/scenario.hpp"
#include "tuneros/simulator/simulation_clock.hpp"
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

bool test_simulation_clock() {
  SimulationClock clock;
  if (!expect(clock.timestamp().microseconds == 0 && clock.tick_count() == 0,
              "Clock must start at timestamp and tick zero")) {
    return false;
  }

  clock.advance();
  if (!expect(clock.timestamp().microseconds == 10'000 && clock.tick_count() == 1,
              "One clock tick must advance exactly one fixed step")) {
    return false;
  }

  clock.advance_ticks(9);
  if (!expect(clock.timestamp().microseconds == 100'000 && clock.tick_count() == 10,
              "N clock ticks must produce an exact integer timestamp")) {
    return false;
  }

  clock.pause();
  clock.advance_ticks(50);
  if (!expect(clock.timestamp().microseconds == 100'000 && clock.tick_count() == 10,
              "A paused clock must not advance")) {
    return false;
  }

  clock.resume();
  clock.advance();
  if (!expect(clock.timestamp().microseconds == 110'000, "A resumed clock must advance again")) {
    return false;
  }

  clock.reset();
  if (!expect(clock.timestamp().microseconds == 0 && clock.tick_count() == 0 && !clock.is_paused(),
              "Reset must clear time, ticks, and pause state")) {
    return false;
  }

  const SimulationClock alternate_clock{SimulationDuration{20'000}};
  if (!expect(alternate_clock.fixed_step().microseconds == 20'000,
              "A positive alternate fixed step must be accepted")) {
    return false;
  }

  try {
    [[maybe_unused]] const SimulationClock invalid_clock{SimulationDuration{0}};
    return expect(false, "A zero fixed step must be rejected");
  } catch (const std::invalid_argument&) {
    return true;
  }
}

bool test_reference_profile() {
  const auto profile = make_e90_335i_n54_manual_profile();
  return expect(is_valid(profile), "The reference profile must pass contract validation") &&
         expect(profile.profile_id == "bmw-e90-335i-n54-2010-manual",
                "The reference profile identifier must be stable") &&
         expect(profile.manufacturer == "BMW" && profile.model == "335i" &&
                    profile.chassis == "E90" && profile.model_year == 2010,
                "The reference vehicle identity must match the Phase 0B contract") &&
         expect(profile.engine_family == "N54" && profile.engine_identifier == "N54B30" &&
                    profile.cylinder_count == 6 && nearly_equal(profile.displacement_liters, 2.979),
                "The reference N54 engine fields must match the documented profile") &&
         expect(
             profile.induction_type == InductionType::kTwinTurbo &&
                 profile.transmission_type == TransmissionType::kManual &&
                 profile.forward_gear_count == 6 && nearly_equal(profile.redline_rpm, 7000.0),
             "The reference induction, transmission, and operating limit must match the contract");
}

bool test_idle_scenario_inputs() {
  const EnvironmentState environment{.ambient_temperature_celsius = 12.0,
                                     .ambient_pressure_kpa_absolute = 95.0};
  const auto first = scenario_inputs_for(ScenarioId::kIdle, SimulationTimestamp{0}, environment);
  const auto later =
      scenario_inputs_for(ScenarioId::kIdle, SimulationTimestamp{5'000'000}, environment);
  return expect(first == later,
                "Stable IDLE stimuli must not depend on wall-clock or tick timing") &&
         expect(first.accelerator_pedal_position == 0.0 &&
                    first.requested_scenario_load == model_parameters::kIdleRequestedScenarioLoad &&
                    first.command_vehicle_stationary && first.environment == environment,
                "IDLE must provide inputs rather than resulting vehicle outputs");
}

bool test_idle_simulation_and_determinism() {
  const auto configuration = make_default_idle_run_configuration();
  VehicleSimulation first{configuration};
  VehicleSimulation second{configuration};

  const auto initial = first.state();
  if (!expect(initial.timestamp.microseconds == 0 &&
                  initial.run_state == SimulationRunState::kRunning && initial.engine_running &&
                  initial.vehicle_speed_meters_per_second == 0.0 && initial.current_gear == 0 &&
                  is_valid(initial, configuration.vehicle_profile),
              "IDLE must begin in a valid, running, stationary, neutral state")) {
    return false;
  }

  first.pause();
  if (!expect(!first.tick() && first.state().timestamp.microseconds == 0 &&
                  first.state().run_state == SimulationRunState::kPaused,
              "Pausing a simulation must prevent state and timestamp advancement")) {
    return false;
  }
  first.resume();

  double previous_coolant = first.state().coolant_temperature_celsius;
  double previous_oil = first.state().oil_temperature_celsius;
  const std::uint64_t expected_ticks =
      configuration.duration.microseconds / configuration.fixed_step.microseconds;

  for (std::uint64_t tick = 1; tick <= expected_ticks; ++tick) {
    if (!expect(first.tick() && second.tick(), "Both deterministic runs must execute every tick")) {
      return false;
    }
    const auto& state = first.state();
    if (!expect(state == second.state(),
                "Identical configurations must produce exactly identical state sequences") ||
        !expect(state.timestamp.microseconds == tick * configuration.fixed_step.microseconds,
                "Every state timestamp must advance by the exact integer fixed step") ||
        !expect(is_valid(state, configuration.vehicle_profile),
                "Every produced IDLE state must satisfy the VehicleState contract") ||
        !expect(state.engine_running && state.vehicle_speed_meters_per_second == 0.0 &&
                    state.current_gear == 0,
                "IDLE must remain engine-running, stationary, and neutral") ||
        !expect(state.coolant_temperature_celsius >= previous_coolant &&
                    state.oil_temperature_celsius >= previous_oil,
                "IDLE coolant and oil temperatures must warm monotonically")) {
      return false;
    }
    previous_coolant = state.coolant_temperature_celsius;
    previous_oil = state.oil_temperature_celsius;
  }

  const auto& final_state = first.state();
  const double coolant_warming =
      final_state.coolant_temperature_celsius - initial.coolant_temperature_celsius;
  const double oil_warming = final_state.oil_temperature_celsius - initial.oil_temperature_celsius;

  if (!expect(final_state.run_state == SimulationRunState::kCompleted && !first.tick() &&
                  first.clock().tick_count() == expected_ticks,
              "IDLE must complete exactly at its configured simulation duration") ||
      !expect(
          final_state.engine_speed_rpm >= 650.0 && final_state.engine_speed_rpm <= 900.0 &&
              final_state.engine_speed_rpm >= 0.0 &&
              nearly_equal(final_state.engine_speed_rpm, model_parameters::kIdleTargetRpm, 1e-6),
          "IDLE engine speed must converge to the documented target region") ||
      !expect(coolant_warming > oil_warming && coolant_warming > 0.0 && oil_warming > 0.0,
              "Coolant must warm faster than oil during the Phase 1A IDLE run") ||
      !expect(
          final_state.coolant_temperature_celsius <
                  model_parameters::kCoolantIdleEquilibriumCelsius &&
              final_state.oil_temperature_celsius < model_parameters::kOilIdleEquilibriumCelsius,
          "Thermal state must approach bounded equilibria without overshoot") ||
      !expect(
          final_state.battery_voltage_volts >= 13.0 && final_state.battery_voltage_volts <= 15.0,
          "Engine-running battery voltage must remain in the documented range")) {
    return false;
  }

  first.reset();
  return expect(first.state() == initial && first.clock().timestamp().microseconds == 0,
                "Simulation reset must restore the deterministic initial state");
}

bool test_time_step_consistency() {
  auto ten_millisecond_configuration = make_default_idle_run_configuration();
  ten_millisecond_configuration.duration = SimulationDuration{30'000'000};
  VehicleSimulation ten_millisecond{ten_millisecond_configuration};
  ten_millisecond.run_to_completion();

  auto twenty_millisecond_configuration = ten_millisecond_configuration;
  twenty_millisecond_configuration.fixed_step = SimulationDuration{20'000};
  VehicleSimulation twenty_millisecond{twenty_millisecond_configuration};
  twenty_millisecond.run_to_completion();

  const auto& first = ten_millisecond.state();
  const auto& second = twenty_millisecond.state();
  return expect(
      nearly_equal(first.engine_speed_rpm, second.engine_speed_rpm, 1e-8) &&
          nearly_equal(first.coolant_temperature_celsius, second.coolant_temperature_celsius,
                       1e-8) &&
          nearly_equal(first.oil_temperature_celsius, second.oil_temperature_celsius, 1e-8) &&
          nearly_equal(first.intake_air_temperature_celsius, second.intake_air_temperature_celsius,
                       1e-8) &&
          nearly_equal(first.battery_voltage_volts, second.battery_voltage_volts, 1e-8),
      "Equivalent durations at reasonable steps must produce tightly consistent state");
}

bool test_unsupported_scenarios() {
  constexpr std::array unsupported{
      ScenarioId::kHighway,
      ScenarioId::kSpirited,
      ScenarioId::kWideOpenThrottlePull,
      ScenarioId::kDynoPull,
  };

  for (const auto scenario : unsupported) {
    auto configuration = make_default_idle_run_configuration();
    configuration.scenario = scenario;
    try {
      [[maybe_unused]] const VehicleSimulation simulation{configuration};
      return expect(false, "Every unsupported Phase 1A scenario must fail clearly");
    } catch (const std::invalid_argument&) {
    }
  }
  return true;
}

}  // namespace

int main() {
  if (!test_simulation_clock() || !test_reference_profile() || !test_idle_scenario_inputs() ||
      !test_idle_simulation_and_determinism() || !test_time_step_consistency() ||
      !test_unsupported_scenarios()) {
    return 1;
  }
  return 0;
}
