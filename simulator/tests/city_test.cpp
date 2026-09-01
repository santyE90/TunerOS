#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string_view>

#include "tuneros/simulator/drivetrain.hpp"
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

bool test_drivetrain_relationship() {
  const auto profile = make_e90_335i_n54_manual_profile();
  const double speed = 10.0;
  const double first = engine_speed_for_gear(speed, 1, profile);
  const double second = engine_speed_for_gear(speed, 2, profile);
  const double third = engine_speed_for_gear(speed, 3, profile);
  const double fourth = engine_speed_for_gear(speed, 4, profile);
  const double fifth = engine_speed_for_gear(speed, 5, profile);
  const double sixth = engine_speed_for_gear(speed, 6, profile);

  return expect(
             first > second && second > third && third > fourth && fourth > fifth && fifth > sixth,
             "At equal road speed, every tested upshift must reduce engine RPM") &&
         expect(engine_speed_for_gear(0.0, 0, profile) == model_parameters::kIdleTargetRpm,
                "Neutral stationary operation must use the idle RPM floor") &&
         expect(engine_speed_for_gear(100.0, 1, profile) == profile.redline_rpm,
                "Synthetic drivetrain RPM must clamp at the profile limit") &&
         expect(city_gear_for_speed(4.49, false) == 1 && city_gear_for_speed(4.5, false) == 2 &&
                    city_gear_for_speed(8.0, false) == 3 && city_gear_for_speed(12.0, false) == 4,
                "CITY shift thresholds must select deterministic forward gears");
}

bool test_city_input_timeline() {
  const EnvironmentState environment{};
  const auto initial = scenario_inputs_for(ScenarioId::kCity, SimulationTimestamp{0}, environment);
  const auto before_first_acceleration = scenario_inputs_for(
      ScenarioId::kCity,
      SimulationTimestamp{model_parameters::kCityFirstDepartureTimestampMicroseconds - 1},
      environment);
  const auto first_acceleration = scenario_inputs_for(
      ScenarioId::kCity,
      SimulationTimestamp{model_parameters::kCityFirstDepartureTimestampMicroseconds}, environment);
  const auto first_cruise = scenario_inputs_for(
      ScenarioId::kCity,
      SimulationTimestamp{model_parameters::kCityFirstCruiseTimestampMicroseconds}, environment);
  const auto first_deceleration = scenario_inputs_for(
      ScenarioId::kCity,
      SimulationTimestamp{model_parameters::kCityFirstDecelerationTimestampMicroseconds},
      environment);
  const auto first_stop = scenario_inputs_for(
      ScenarioId::kCity,
      SimulationTimestamp{model_parameters::kCityFirstStopIntentTimestampMicroseconds},
      environment);
  const auto second_acceleration = scenario_inputs_for(
      ScenarioId::kCity,
      SimulationTimestamp{model_parameters::kCitySecondDepartureTimestampMicroseconds},
      environment);
  const auto second_cruise = scenario_inputs_for(
      ScenarioId::kCity,
      SimulationTimestamp{model_parameters::kCitySecondCruiseTimestampMicroseconds}, environment);
  const auto final_deceleration = scenario_inputs_for(
      ScenarioId::kCity,
      SimulationTimestamp{model_parameters::kCityFinalDecelerationTimestampMicroseconds},
      environment);
  const auto final_stop = scenario_inputs_for(
      ScenarioId::kCity,
      SimulationTimestamp{model_parameters::kCityFinalStopIntentTimestampMicroseconds},
      environment);

  return expect(initial.command_vehicle_stationary && initial.accelerator_pedal_position == 0.0 &&
                    before_first_acceleration.command_vehicle_stationary,
                "CITY must retain stationary idle inputs until its first exact boundary") &&
         expect(!first_acceleration.command_vehicle_stationary &&
                    first_acceleration.accelerator_pedal_position ==
                        model_parameters::kCityFirstAccelerationAccelerator &&
                    first_acceleration.requested_scenario_load ==
                        model_parameters::kCityFirstAccelerationLoad,
                "CITY first departure inputs must begin at the documented timestamp") &&
         expect(first_cruise.accelerator_pedal_position ==
                        model_parameters::kCityFirstCruiseAccelerator &&
                    first_cruise.requested_scenario_load == model_parameters::kCityFirstCruiseLoad,
                "CITY first cruise inputs must begin at the documented timestamp") &&
         expect(!first_deceleration.command_vehicle_stationary &&
                    first_deceleration.accelerator_pedal_position == 0.0,
                "CITY coast phase must remove accelerator without forcing speed") &&
         expect(first_stop.command_vehicle_stationary,
                "CITY first stop intent must begin at the documented timestamp") &&
         expect(second_acceleration.accelerator_pedal_position ==
                    model_parameters::kCitySecondAccelerationAccelerator,
                "CITY second departure must use its documented input") &&
         expect(
             second_cruise.accelerator_pedal_position ==
                     model_parameters::kCitySecondCruiseAccelerator &&
                 second_cruise.requested_scenario_load == model_parameters::kCitySecondCruiseLoad,
             "CITY second cruise inputs must begin at the documented timestamp") &&
         expect(!final_deceleration.command_vehicle_stationary &&
                    final_deceleration.accelerator_pedal_position == 0.0,
                "CITY final coast phase must begin at the documented timestamp") &&
         expect(
             final_stop.command_vehicle_stationary && final_stop.accelerator_pedal_position == 0.0,
             "CITY final stop intent must be explicit and deterministic");
}

struct CityRunSummary {
  VehicleState final_state;
  double peak_speed_meters_per_second{};
  double speed_at_ten_seconds{};
  double speed_at_thirty_two_seconds{};
  double speed_at_forty_five_seconds{};
  bool observed_forward_gear{};
  bool observed_upshift_rpm_drop{};
  bool observed_first_stop{};
  bool observed_load_pressure_response{};
};

CityRunSummary run_city_and_validate(SimulationDuration fixed_step) {
  auto configuration = make_default_city_run_configuration();
  configuration.fixed_step = fixed_step;
  VehicleSimulation simulation{configuration};
  VehicleSimulation duplicate{configuration};

  CityRunSummary summary;
  auto previous_state = simulation.state();
  while (simulation.tick()) {
    if (!duplicate.tick() || simulation.state() != duplicate.state()) {
      std::cerr << "Identical CITY runs diverged\n";
      return {};
    }

    const auto& state = simulation.state();
    if (!is_valid(state, configuration.vehicle_profile) || !state.engine_running ||
        state.vehicle_speed_meters_per_second < 0.0 || state.current_gear < 0 ||
        state.current_gear >
            static_cast<std::int8_t>(configuration.vehicle_profile.forward_gear_count) ||
        state.manifold_pressure_kpa_absolute < 0.0 ||
        state.manifold_pressure_kpa_absolute > state.ambient_pressure_kpa_absolute ||
        !std::isfinite(state.actual_boost_kpa_gauge())) {
      std::cerr << "CITY produced an invalid physical/logical state\n";
      return {};
    }

    summary.peak_speed_meters_per_second =
        std::max(summary.peak_speed_meters_per_second, state.vehicle_speed_meters_per_second);
    summary.observed_forward_gear = summary.observed_forward_gear || state.current_gear > 0;
    summary.observed_load_pressure_response =
        summary.observed_load_pressure_response ||
        (state.accelerator_pedal_position > 0.0 &&
         state.manifold_pressure_kpa_absolute >
             state.ambient_pressure_kpa_absolute *
                 model_parameters::kIdleManifoldPressureFractionOfAmbient);
    if (state.current_gear > previous_state.current_gear && previous_state.current_gear > 0 &&
        state.engine_speed_rpm < previous_state.engine_speed_rpm) {
      summary.observed_upshift_rpm_drop = true;
    }
    if (state.timestamp.microseconds >=
            model_parameters::kCityFirstStopIntentTimestampMicroseconds &&
        state.timestamp.microseconds <
            model_parameters::kCitySecondDepartureTimestampMicroseconds &&
        state.vehicle_speed_meters_per_second == 0.0 && state.current_gear == 0) {
      summary.observed_first_stop = true;
    }
    if (state.timestamp.microseconds == 10'000'000) {
      summary.speed_at_ten_seconds = state.vehicle_speed_meters_per_second;
    }
    if (state.timestamp.microseconds == 32'000'000) {
      summary.speed_at_thirty_two_seconds = state.vehicle_speed_meters_per_second;
    }
    if (state.timestamp.microseconds == 45'000'000) {
      summary.speed_at_forty_five_seconds = state.vehicle_speed_meters_per_second;
    }
    previous_state = state;
  }
  summary.final_state = simulation.state();
  return summary;
}

bool test_city_motion_and_determinism() {
  const auto configuration = make_default_city_run_configuration();
  VehicleSimulation simulation{configuration};
  const auto initial = simulation.state();
  if (!expect(initial.engine_running &&
                  initial.engine_speed_rpm == model_parameters::kIdleTargetRpm &&
                  initial.vehicle_speed_meters_per_second == 0.0 && initial.current_gear == 0,
              "CITY must begin running, stationary, neutral, and at idle RPM")) {
    return false;
  }

  const auto summary = run_city_and_validate(kBaseSimulationStep);
  if (!expect(summary.speed_at_ten_seconds > 0.0,
              "CITY speed must rise during the first acceleration phase") ||
      !expect(summary.speed_at_thirty_two_seconds > summary.speed_at_ten_seconds,
              "CITY cruise phase must remain bounded while preserving forward motion") ||
      !expect(summary.speed_at_forty_five_seconds < summary.speed_at_thirty_two_seconds,
              "CITY speed must fall during the first deceleration") ||
      !expect(
          summary.peak_speed_meters_per_second > 8.0 && summary.peak_speed_meters_per_second < 15.0,
          "CITY must produce a bounded, believable synthetic peak speed") ||
      !expect(summary.observed_forward_gear && summary.observed_upshift_rpm_drop,
              "CITY must select forward gears and reduce RPM on an upshift") ||
      !expect(summary.observed_load_pressure_response,
              "CITY manifold pressure must move toward ambient under load") ||
      !expect(summary.observed_first_stop,
              "CITY must reach a deterministic neutral stop between trips") ||
      !expect(summary.final_state.run_state == SimulationRunState::kCompleted &&
                  summary.final_state.timestamp.microseconds ==
                      model_parameters::kDefaultCityDurationMicroseconds &&
                  summary.final_state.vehicle_speed_meters_per_second == 0.0 &&
                  summary.final_state.current_gear == 0 &&
                  summary.final_state.engine_speed_rpm == model_parameters::kIdleTargetRpm,
              "CITY must finish at an exact stationary neutral idle state")) {
    return false;
  }

  simulation.run_to_completion();
  const auto completed = simulation.state();
  simulation.reset();
  if (!expect(simulation.state() == initial,
              "CITY reset must restore the exact deterministic initial state")) {
    return false;
  }
  simulation.run_to_completion();
  return expect(simulation.state() == completed,
                "CITY rerun after reset must reproduce the exact final state");
}

bool test_city_cross_step_consistency() {
  const auto ten = run_city_and_validate(SimulationDuration{10'000});
  const auto twenty = run_city_and_validate(SimulationDuration{20'000});
  const auto fifteen = run_city_and_validate(SimulationDuration{15'000});

  return expect(nearly_equal(ten.peak_speed_meters_per_second, twenty.peak_speed_meters_per_second,
                             0.05) &&
                    nearly_equal(ten.peak_speed_meters_per_second,
                                 fifteen.peak_speed_meters_per_second, 0.05),
                "CITY peak speed must remain consistent across 10, 20, and 15 ms steps") &&
         expect(ten.final_state.vehicle_speed_meters_per_second == 0.0 &&
                    twenty.final_state.vehicle_speed_meters_per_second == 0.0 &&
                    fifteen.final_state.vehicle_speed_meters_per_second == 0.0 &&
                    ten.final_state.engine_speed_rpm == model_parameters::kIdleTargetRpm &&
                    twenty.final_state.engine_speed_rpm == model_parameters::kIdleTargetRpm &&
                    fifteen.final_state.engine_speed_rpm == model_parameters::kIdleTargetRpm,
                "Every reasonable CITY step must finish at stationary idle") &&
         expect(nearly_equal(ten.final_state.coolant_temperature_celsius,
                             twenty.final_state.coolant_temperature_celsius, 1e-8) &&
                    nearly_equal(ten.final_state.coolant_temperature_celsius,
                                 fifteen.final_state.coolant_temperature_celsius, 1e-8) &&
                    nearly_equal(ten.final_state.oil_temperature_celsius,
                                 twenty.final_state.oil_temperature_celsius, 1e-8) &&
                    nearly_equal(ten.final_state.oil_temperature_celsius,
                                 fifteen.final_state.oil_temperature_celsius, 1e-8),
                "CITY thermal state must remain tightly consistent across step sizes");
}

bool test_unsupported_scenarios_after_phase1c() {
  constexpr std::array unsupported{
      ScenarioId::kHighway,
      ScenarioId::kSpirited,
      ScenarioId::kWideOpenThrottlePull,
      ScenarioId::kDynoPull,
  };
  for (const auto scenario : unsupported) {
    auto configuration = make_default_city_run_configuration();
    configuration.scenario = scenario;
    try {
      [[maybe_unused]] const VehicleSimulation simulation{configuration};
      return expect(false, "Unsupported post-Phase 1C scenarios must fail clearly");
    } catch (const std::invalid_argument&) {
    }
  }
  return true;
}

}  // namespace

int main() {
  if (!test_drivetrain_relationship() || !test_city_input_timeline() ||
      !test_city_motion_and_determinism() || !test_city_cross_step_consistency() ||
      !test_unsupported_scenarios_after_phase1c()) {
    return 1;
  }
  return 0;
}
