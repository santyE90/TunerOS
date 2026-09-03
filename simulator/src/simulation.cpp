#include "tuneros/simulator/simulation.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>

#include "tuneros/simulator/drivetrain.hpp"
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

[[nodiscard]] bool is_supported(ScenarioId scenario) noexcept {
  return scenario == ScenarioId::kIdle || scenario == ScenarioId::kColdStart ||
         scenario == ScenarioId::kWarmup || scenario == ScenarioId::kCity;
}

[[nodiscard]] double cold_start_fraction(double requested_scenario_load) noexcept {
  using namespace model_parameters;
  const double load_range = kColdStartElevatedRequestedScenarioLoad - kIdleRequestedScenarioLoad;
  return std::clamp((requested_scenario_load - kIdleRequestedScenarioLoad) / load_range, 0.0, 1.0);
}

void validate_configuration(const SimulationRunConfiguration& configuration) {
  if (!is_valid(configuration.vehicle_profile)) {
    throw std::invalid_argument("simulation vehicle profile is invalid");
  }
  if (!is_valid(configuration.environment)) {
    throw std::invalid_argument("simulation environment is invalid");
  }
  if (!is_valid(configuration.initial_conditions, configuration.vehicle_profile)) {
    throw std::invalid_argument("simulation initial conditions are invalid");
  }
  if (!are_valid(configuration.faults)) {
    throw std::invalid_argument(
        "fault configurations require unique IDs and deactivation after activation");
  }
  if (!is_supported(configuration.scenario)) {
    throw std::invalid_argument("scenario is not implemented in Phase 1C");
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
  if (configuration.scenario == ScenarioId::kColdStart &&
      (model_parameters::kColdStartRequestTimestampMicroseconds %
               configuration.fixed_step.microseconds !=
           0 ||
       model_parameters::kColdStartStabilizationDurationMicroseconds %
               configuration.fixed_step.microseconds !=
           0)) {
    throw std::invalid_argument("cold-start schedule boundaries must align with the fixed step");
  }
  if (configuration.initial_conditions.vehicle_speed_meters_per_second != 0.0 ||
      configuration.initial_conditions.current_gear != 0) {
    throw std::invalid_argument("implemented scenarios must start stationary and neutral");
  }

  const bool should_start_running = configuration.scenario != ScenarioId::kColdStart;
  if (configuration.initial_conditions.engine_running != should_start_running) {
    throw std::invalid_argument("initial engine state is inconsistent with the scenario");
  }
}

[[nodiscard]] VehicleState make_initial_state(const SimulationRunConfiguration& configuration) {
  using namespace model_parameters;

  const auto& initial = configuration.initial_conditions;
  const auto inputs =
      scenario_inputs_for(configuration.scenario, SimulationTimestamp{}, configuration.environment);
  const double startup_fraction = cold_start_fraction(inputs.requested_scenario_load);

  return {
      .timestamp = {},
      .run_state = SimulationRunState::kRunning,
      .accelerator_pedal_position = inputs.accelerator_pedal_position,
      .requested_scenario_load = inputs.requested_scenario_load,
      .engine_running = initial.engine_running,
      .engine_speed_rpm = initial.engine_speed_rpm,
      .engine_load = initial.engine_running
                         ? kIdleEngineLoad + kColdStartEngineLoadIncrease * startup_fraction
                         : 0.0,
      .throttle_position =
          initial.engine_running
              ? kIdleThrottlePosition + kColdStartThrottleIncrease * startup_fraction
              : 0.0,
      .vehicle_speed_meters_per_second = initial.vehicle_speed_meters_per_second,
      .current_gear = initial.current_gear,
      .ambient_pressure_kpa_absolute = configuration.environment.ambient_pressure_kpa_absolute,
      .manifold_pressure_kpa_absolute =
          initial.engine_running ? configuration.environment.ambient_pressure_kpa_absolute *
                                       kIdleManifoldPressureFractionOfAmbient
                                 : configuration.environment.ambient_pressure_kpa_absolute,
      .requested_boost_kpa_gauge = 0.0,
      .coolant_temperature_celsius = initial.coolant_temperature_celsius,
      .oil_temperature_celsius = initial.oil_temperature_celsius,
      .intake_air_temperature_celsius = initial.intake_air_temperature_celsius,
      .lambda = kIdleLambda,
      .ignition_advance_degrees = kIdleIgnitionAdvanceDegrees,
      .timing_correction_degrees = 0.0,
      .battery_voltage_volts = initial.battery_voltage_volts,
  };
}

void apply_scenario_inputs(VehicleState& state, const ScenarioInputs& inputs) noexcept {
  state.accelerator_pedal_position = inputs.accelerator_pedal_position;
  state.requested_scenario_load = inputs.requested_scenario_load;
  state.ambient_pressure_kpa_absolute = inputs.environment.ambient_pressure_kpa_absolute;
}

void evolve_vehicle_state(VehicleState& state, const ScenarioInputs& inputs, ScenarioId scenario,
                          const VehicleProfile& profile, const ActiveFaults& active_faults,
                          double delta_time_seconds) noexcept {
  using namespace model_parameters;

  apply_scenario_inputs(state, inputs);
  if (!state.engine_running && inputs.engine_start_requested) {
    state.engine_running = true;
  }

  if (!state.engine_running) {
    state.engine_speed_rpm = 0.0;
    state.engine_load = 0.0;
    state.throttle_position = 0.0;
    state.manifold_pressure_kpa_absolute = inputs.environment.ambient_pressure_kpa_absolute;
    state.requested_boost_kpa_gauge = 0.0;
    state.intake_air_temperature_celsius = approach(
        state.intake_air_temperature_celsius, inputs.environment.ambient_temperature_celsius,
        kIntakeAirTimeConstantSeconds, delta_time_seconds);
    state.battery_voltage_volts = approach(state.battery_voltage_volts, kRestingBatteryVoltageVolts,
                                           kBatteryVoltageTimeConstantSeconds, delta_time_seconds);
    state.lambda = kIdleLambda;
    state.ignition_advance_degrees = kIdleIgnitionAdvanceDegrees;
    state.timing_correction_degrees = 0.0;
    return;
  }

  if (scenario == ScenarioId::kCity) {
    const auto drivetrain = evolve_city_drivetrain(
        state.vehicle_speed_meters_per_second, inputs.accelerator_pedal_position,
        inputs.command_vehicle_stationary, delta_time_seconds, profile);
    state.vehicle_speed_meters_per_second = drivetrain.vehicle_speed_meters_per_second;
    state.current_gear = drivetrain.selected_gear;
    state.engine_speed_rpm = drivetrain.engine_speed_rpm;
    state.engine_load =
        std::clamp(kCityEngineLoadOffset + inputs.requested_scenario_load, 0.0, 1.0);
    state.throttle_position = std::clamp(
        kIdleThrottlePosition + kCityThrottlePerAccelerator * inputs.accelerator_pedal_position,
        0.0, 1.0);

    const double load_above_idle =
        std::clamp((inputs.requested_scenario_load - kIdleRequestedScenarioLoad) /
                       (1.0 - kIdleRequestedScenarioLoad),
                   0.0, 1.0);
    const double manifold_pressure_fraction =
        kIdleManifoldPressureFractionOfAmbient +
        (kCityMaximumManifoldPressureFractionOfAmbient - kIdleManifoldPressureFractionOfAmbient) *
            load_above_idle;
    state.manifold_pressure_kpa_absolute =
        inputs.environment.ambient_pressure_kpa_absolute * manifold_pressure_fraction;
  } else {
    state.vehicle_speed_meters_per_second = 0.0;
    state.current_gear = 0;
    const double startup_fraction = cold_start_fraction(inputs.requested_scenario_load);
    const double engine_speed_target =
        kIdleTargetRpm + (kColdStartElevatedRpmTarget - kIdleTargetRpm) * startup_fraction;
    const double rpm_time_constant = startup_fraction > 0.0
                                         ? kColdStartRpmResponseTimeConstantSeconds
                                         : kIdleRpmTimeConstantSeconds;
    state.engine_speed_rpm = approach(state.engine_speed_rpm, engine_speed_target,
                                      rpm_time_constant, delta_time_seconds);
    state.engine_load = kIdleEngineLoad + kColdStartEngineLoadIncrease * startup_fraction;
    state.throttle_position = kIdleThrottlePosition + kColdStartThrottleIncrease * startup_fraction;
    state.manifold_pressure_kpa_absolute =
        inputs.environment.ambient_pressure_kpa_absolute * kIdleManifoldPressureFractionOfAmbient;
  }
  state.requested_boost_kpa_gauge = 0.0;

  const double coolant_equilibrium = active_faults.cooling_system_degradation
                                         ? fault_parameters::kDegradedCoolingEquilibriumCelsius
                                         : kCoolantIdleEquilibriumCelsius;
  const double coolant_time_constant = active_faults.cooling_system_degradation
                                           ? fault_parameters::kDegradedCoolingTimeConstantSeconds
                                           : kCoolantWarmupTimeConstantSeconds;
  state.coolant_temperature_celsius =
      approach(state.coolant_temperature_celsius, coolant_equilibrium, coolant_time_constant,
               delta_time_seconds);
  state.oil_temperature_celsius =
      approach(state.oil_temperature_celsius, kOilIdleEquilibriumCelsius,
               kOilWarmupTimeConstantSeconds, delta_time_seconds);
  const double intake_air_equilibrium =
      inputs.environment.ambient_temperature_celsius + kIntakeAirAboveAmbientAtIdleCelsius;
  state.intake_air_temperature_celsius =
      approach(state.intake_air_temperature_celsius, intake_air_equilibrium,
               kIntakeAirTimeConstantSeconds, delta_time_seconds);

  state.lambda = kIdleLambda;
  state.ignition_advance_degrees = kIdleIgnitionAdvanceDegrees;
  state.timing_correction_degrees = 0.0;
  const double charging_target = active_faults.charging_system_failure
                                     ? fault_parameters::kFailedChargingVoltageVolts
                                     : kChargingVoltageVolts;
  const double charging_time_constant = active_faults.charging_system_failure
                                            ? fault_parameters::kFailedChargingTimeConstantSeconds
                                            : kBatteryVoltageTimeConstantSeconds;
  state.battery_voltage_volts = approach(state.battery_voltage_volts, charging_target,
                                         charging_time_constant, delta_time_seconds);
}

[[nodiscard]] SimulationRunConfiguration make_run_configuration(
    ScenarioId scenario, SimulationDuration duration, EnvironmentState environment,
    SimulationInitialConditions initial_conditions) {
  return {
      .vehicle_profile = make_e90_335i_n54_manual_profile(),
      .scenario = scenario,
      .duration = duration,
      .fixed_step = kBaseSimulationStep,
      .environment = environment,
      .initial_conditions = initial_conditions,
  };
}

}  // namespace

SimulationRunConfiguration make_default_idle_run_configuration(EnvironmentState environment) {
  return make_run_configuration(
      ScenarioId::kIdle, SimulationDuration{model_parameters::kDefaultIdleDurationMicroseconds},
      environment, make_idle_initial_conditions(environment));
}

SimulationRunConfiguration make_default_cold_start_run_configuration(EnvironmentState environment) {
  return make_run_configuration(
      ScenarioId::kColdStart,
      SimulationDuration{model_parameters::kDefaultColdStartDurationMicroseconds}, environment,
      make_cold_start_initial_conditions(environment));
}

SimulationRunConfiguration make_default_warmup_run_configuration(EnvironmentState environment) {
  return make_run_configuration(
      ScenarioId::kWarmup, SimulationDuration{model_parameters::kDefaultWarmupDurationMicroseconds},
      environment, make_warmup_initial_conditions(environment));
}

SimulationRunConfiguration make_default_city_run_configuration(EnvironmentState environment) {
  return make_run_configuration(
      ScenarioId::kCity, SimulationDuration{model_parameters::kDefaultCityDurationMicroseconds},
      environment, make_city_initial_conditions(environment));
}

VehicleSimulation::VehicleSimulation(SimulationRunConfiguration configuration)
    : configuration_(std::move(configuration)), clock_(configuration_.fixed_step) {
  validate_configuration(configuration_);
  initial_state_ = make_initial_state(configuration_);
  if (!is_valid(initial_state_, configuration_.vehicle_profile)) {
    throw std::invalid_argument("initial vehicle state is invalid");
  }
  state_ = initial_state_;
}

bool VehicleSimulation::tick() {
  if (clock_.is_paused() || state_.run_state == SimulationRunState::kCompleted) {
    return false;
  }

  clock_.advance();
  const auto inputs =
      scenario_inputs_for(configuration_.scenario, clock_.timestamp(), configuration_.environment);
  const double delta_time_seconds =
      static_cast<double>(clock_.fixed_step().microseconds) / kMicrosecondsPerSecond;
  const auto active_faults = active_faults_at(configuration_.faults, clock_.timestamp());
  evolve_vehicle_state(state_, inputs, configuration_.scenario, configuration_.vehicle_profile,
                       active_faults, delta_time_seconds);
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
