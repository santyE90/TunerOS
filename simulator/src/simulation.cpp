#include "tuneros/simulator/simulation.hpp"

#include <cmath>
#include <stdexcept>
#include <utility>

#include "tuneros/simulator/model_parameters.hpp"
#include "tuneros/simulator/scenario.hpp"
#include "tuneros/simulator/vehicle_profiles.hpp"

namespace tuneros::simulator {
namespace {

constexpr double kMicrosecondsPerSecond = 1'000'000.0;

[[nodiscard]] double approach(double current, double target, double time_constant_seconds,
                              double delta_time_seconds) noexcept {
  const double retained_difference = std::exp(-delta_time_seconds / time_constant_seconds);
  return target + (current - target) * retained_difference;
}

void validate_configuration(const SimulationRunConfiguration& configuration) {
  if (!is_valid(configuration.vehicle_profile)) {
    throw std::invalid_argument("simulation vehicle profile is invalid");
  }
  if (!is_valid(configuration.environment)) {
    throw std::invalid_argument("simulation environment is invalid");
  }
  if (configuration.scenario != ScenarioId::kIdle) {
    throw std::invalid_argument("scenario is not implemented in Phase 1A");
  }
  if (configuration.duration.microseconds == 0) {
    throw std::invalid_argument("simulation duration must be positive");
  }
  if (configuration.fixed_step.microseconds == 0) {
    throw std::invalid_argument("simulation fixed step must be positive");
  }
  if (configuration.duration.microseconds % configuration.fixed_step.microseconds != 0) {
    throw std::invalid_argument("simulation duration must be an integer number of fixed steps");
  }
}

[[nodiscard]] VehicleState make_idle_initial_state(const EnvironmentState& environment) {
  using namespace model_parameters;

  return {
      .timestamp = {},
      .run_state = SimulationRunState::kRunning,
      .accelerator_pedal_position = 0.0,
      .requested_scenario_load = kIdleRequestedScenarioLoad,
      .engine_running = true,
      .engine_speed_rpm = kInitialEngineSpeedRpm,
      .engine_load = kIdleEngineLoad,
      .throttle_position = kIdleThrottlePosition,
      .vehicle_speed_meters_per_second = 0.0,
      .current_gear = 0,
      .ambient_pressure_kpa_absolute = environment.ambient_pressure_kpa_absolute,
      .manifold_pressure_kpa_absolute =
          environment.ambient_pressure_kpa_absolute * kIdleManifoldPressureFractionOfAmbient,
      .requested_boost_kpa_gauge = 0.0,
      .coolant_temperature_celsius =
          environment.ambient_temperature_celsius + kInitialCoolantAboveAmbientCelsius,
      .oil_temperature_celsius =
          environment.ambient_temperature_celsius + kInitialOilAboveAmbientCelsius,
      .intake_air_temperature_celsius =
          environment.ambient_temperature_celsius + kInitialIntakeAirAboveAmbientCelsius,
      .lambda = kIdleLambda,
      .ignition_advance_degrees = kIdleIgnitionAdvanceDegrees,
      .timing_correction_degrees = 0.0,
      .battery_voltage_volts = kInitialBatteryVoltageVolts,
  };
}

void evolve_idle_state(VehicleState& state, const ScenarioInput& input,
                       double delta_time_seconds) noexcept {
  using namespace model_parameters;

  state.accelerator_pedal_position = input.accelerator_pedal_position;
  state.requested_scenario_load = input.requested_scenario_load;
  state.ambient_pressure_kpa_absolute = input.environment.ambient_pressure_kpa_absolute;

  if (input.command_vehicle_stationary) {
    state.vehicle_speed_meters_per_second = 0.0;
    state.current_gear = 0;
  }

  state.engine_running = true;
  state.engine_speed_rpm = approach(state.engine_speed_rpm, kIdleTargetRpm,
                                    kIdleRpmTimeConstantSeconds, delta_time_seconds);
  state.engine_load = kIdleEngineLoad;
  state.throttle_position = kIdleThrottlePosition;

  state.manifold_pressure_kpa_absolute =
      input.environment.ambient_pressure_kpa_absolute * kIdleManifoldPressureFractionOfAmbient;
  state.requested_boost_kpa_gauge = 0.0;

  state.coolant_temperature_celsius =
      approach(state.coolant_temperature_celsius, kCoolantIdleEquilibriumCelsius,
               kCoolantWarmupTimeConstantSeconds, delta_time_seconds);
  state.oil_temperature_celsius =
      approach(state.oil_temperature_celsius, kOilIdleEquilibriumCelsius,
               kOilWarmupTimeConstantSeconds, delta_time_seconds);
  const double intake_air_equilibrium =
      input.environment.ambient_temperature_celsius + kIntakeAirAboveAmbientAtIdleCelsius;
  state.intake_air_temperature_celsius =
      approach(state.intake_air_temperature_celsius, intake_air_equilibrium,
               kIntakeAirTimeConstantSeconds, delta_time_seconds);

  state.lambda = kIdleLambda;
  state.ignition_advance_degrees = kIdleIgnitionAdvanceDegrees;
  state.timing_correction_degrees = 0.0;
  state.battery_voltage_volts = approach(state.battery_voltage_volts, kChargingVoltageVolts,
                                         kBatteryVoltageTimeConstantSeconds, delta_time_seconds);
}

}  // namespace

SimulationRunConfiguration make_default_idle_run_configuration() {
  return {
      .vehicle_profile = make_e90_335i_n54_manual_profile(),
      .scenario = ScenarioId::kIdle,
      .duration = SimulationDuration{60'000'000},
      .fixed_step = kBaseSimulationStep,
      .environment = EnvironmentState{},
  };
}

VehicleSimulation::VehicleSimulation(SimulationRunConfiguration configuration)
    : configuration_(std::move(configuration)), clock_(configuration_.fixed_step) {
  validate_configuration(configuration_);
  initial_state_ = make_idle_initial_state(configuration_.environment);
  if (!is_valid(initial_state_, configuration_.vehicle_profile)) {
    throw std::invalid_argument("initial vehicle state is invalid");
  }
  state_ = initial_state_;
}

bool VehicleSimulation::tick() {
  if (clock_.is_paused() || state_.run_state == SimulationRunState::kCompleted) {
    return false;
  }

  const auto input = idle_scenario_input(clock_.timestamp(), configuration_.environment);
  const double delta_time_seconds =
      static_cast<double>(clock_.fixed_step().microseconds) / kMicrosecondsPerSecond;
  evolve_idle_state(state_, input, delta_time_seconds);
  clock_.advance();
  state_.timestamp = clock_.timestamp();
  state_.run_state = state_.timestamp.microseconds == configuration_.duration.microseconds
                         ? SimulationRunState::kCompleted
                         : SimulationRunState::kRunning;
  return true;
}

std::uint64_t VehicleSimulation::advance_ticks(std::uint64_t count) {
  std::uint64_t advanced{};
  while (advanced < count && tick()) {
    ++advanced;
  }
  return advanced;
}

std::uint64_t VehicleSimulation::run_to_completion() {
  const auto ticks_remaining =
      (configuration_.duration.microseconds - state_.timestamp.microseconds) /
      configuration_.fixed_step.microseconds;
  return advance_ticks(ticks_remaining);
}

void VehicleSimulation::pause() noexcept {
  if (state_.run_state == SimulationRunState::kCompleted) {
    return;
  }
  clock_.pause();
  state_.run_state = SimulationRunState::kPaused;
}

void VehicleSimulation::resume() noexcept {
  if (state_.run_state != SimulationRunState::kPaused) {
    return;
  }
  clock_.resume();
  state_.run_state = SimulationRunState::kRunning;
}

void VehicleSimulation::reset() noexcept {
  clock_.reset();
  state_ = initial_state_;
}

}  // namespace tuneros::simulator
