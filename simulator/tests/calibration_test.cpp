#include "tuneros/simulator/calibration.hpp"

#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string_view>
#include <vector>

#include "tuneros/simulator/model_parameters.hpp"
#include "tuneros/simulator/scenario.hpp"
#include "tuneros/simulator/simulation.hpp"

namespace {

using namespace tuneros::simulator;

bool expect(bool condition, std::string_view message) {
  if (!condition) {
    std::cerr << message << '\n';
  }
  return condition;
}

bool near(double left, double right, double tolerance = 1e-12) {
  return std::abs(left - right) <= tolerance;
}

bool test_table_lookup_and_clamping() {
  const Table1D line{"line", "value", Axis1D{"x", "unit", {0.0, 10.0}}, {2.0, 12.0}};
  const Table2D surface{"surface",
                        "value",
                        Axis1D{"row", "unit", {0.0, 10.0}},
                        Axis1D{"column", "unit", {0.0, 20.0}},
                        {0.0, 20.0, 10.0, 30.0}};
  return expect(line.lookup(0.0) == 2.0 && line.lookup(5.0) == 7.0 && line.lookup(-1.0) == 2.0 &&
                    line.lookup(20.0) == 12.0,
                "1D lookup must interpolate and clamp at both edges") &&
         expect(surface.lookup(0.0, 0.0) == 0.0 && surface.lookup(10.0, 20.0) == 30.0 &&
                    surface.lookup(5.0, 10.0) == 15.0 && surface.lookup(-1.0, 99.0) == 20.0,
                "2D lookup must use deterministic bilinear interpolation and edge clamping") &&
         expect(surface.lookup(5.0, 10.0) == surface.lookup(5.0, 10.0),
                "Repeated map lookup must be exact");
}

bool test_invalid_tables_rejected() {
  const auto rejects = [](auto operation) {
    try {
      operation();
      return false;
    } catch (const std::invalid_argument&) {
      return true;
    }
  };
  return expect(
      rejects([] { [[maybe_unused]] Axis1D axis{"x", "unit", {1.0, 0.0}}; }) &&
          rejects([] { [[maybe_unused]] Axis1D axis{"x", "unit", {1.0, 1.0}}; }) && rejects([] {
            [[maybe_unused]] Axis1D axis{
                "x", "unit", {0.0, std::numeric_limits<double>::infinity()}};
          }) &&
          rejects([] {
            [[maybe_unused]] Table1D table{"x", "unit", Axis1D{"x", "unit", {0.0, 1.0}}, {1.0}};
          }) &&
          rejects([] {
            [[maybe_unused]] Table2D table{"x",
                                           "unit",
                                           Axis1D{"x", "unit", {0.0, 1.0}},
                                           Axis1D{"y", "unit", {0.0, 1.0}},
                                           {1.0, 2.0, 3.0}};
          }) &&
          rejects([] {
            const Table1D table{"x", "unit", Axis1D{"x", "unit", {0.0, 1.0}}, {0.0, 1.0}};
            [[maybe_unused]] const auto value =
                table.lookup(std::numeric_limits<double>::quiet_NaN());
          }) &&
          rejects([] {
            const Table2D table{"x",
                                "unit",
                                Axis1D{"x", "unit", {0.0, 1.0}},
                                Axis1D{"y", "unit", {0.0, 1.0}},
                                {0.0, 1.0, 1.0, 2.0}};
            [[maybe_unused]] const auto value =
                table.lookup(std::numeric_limits<double>::infinity(), 0.5);
          }),
      "Axes and tables must reject invalid ordering, finiteness, and dimensions");
}

bool test_profiles_and_wot_schedule() {
  const auto& stock = calibration_profile(CalibrationId::kStock);
  const auto& stage1 = calibration_profile(CalibrationId::kStage1);
  const auto before =
      scenario_inputs_for(ScenarioId::kWideOpenThrottlePull, SimulationTimestamp{1'990'000}, {});
  const auto onset =
      scenario_inputs_for(ScenarioId::kWideOpenThrottlePull, SimulationTimestamp{2'000'000}, {});
  return expect(stock.profile_id == "stock" && stage1.profile_id == "stage-1" &&
                    stock.revision == 1 && stage1.revision == 1 && stock.synthetic &&
                    stage1.synthetic && calibration_profiles().size() == 2,
                "Exactly two stable synthetic revision-one profiles must exist") &&
         expect(make_default_wot_pull_run_configuration().calibration == CalibrationId::kStock,
                "Stock must remain the default calibration") &&
         expect(calibration_id_from_name("stock") == CalibrationId::kStock &&
                    calibration_id_from_name("stage-1") == CalibrationId::kStage1 &&
                    !calibration_id_from_name("unknown").has_value(),
                "Calibration names must parse explicitly") &&
         expect(stage1.boost_target_kpa_gauge.lookup(4'000.0, 1.0) >
                        stock.boost_target_kpa_gauge.lookup(4'000.0, 1.0) &&
                    stage1.lambda_target.lookup(1.0) < stock.lambda_target.lookup(1.0),
                "Stage 1 maps must deliberately differ under high load") &&
         expect(before.accelerator_pedal_position == model_parameters::kWotPullPreloadAccelerator &&
                    onset.accelerator_pedal_position == model_parameters::kWotPullAccelerator &&
                    !before.command_vehicle_stationary && !onset.command_vehicle_stationary,
                "WOT_PULL demand must change at the exact deterministic boundary");
}

bool test_wot_profile_determinism_and_difference() {
  const auto run = [](CalibrationId id) {
    VehicleSimulation simulation{make_default_wot_pull_run_configuration({}, id)};
    std::vector<VehicleState> states{simulation.state()};
    while (simulation.tick()) {
      states.push_back(simulation.state());
    }
    return states;
  };
  const auto stock_first = run(CalibrationId::kStock);
  const auto stock_second = run(CalibrationId::kStock);
  const auto stage_first = run(CalibrationId::kStage1);
  const auto stage_second = run(CalibrationId::kStage1);
  const auto& stock = stock_first.back();
  const auto& stage1 = stage_first.back();
  return expect(stock_first == stock_second && stage_first == stage_second,
                "Each profile must reproduce its exact VehicleState sequence") &&
         expect(stock_first.size() == 1'201 &&
                    stock_first.back().timestamp.microseconds ==
                        model_parameters::kDefaultWotPullDurationMicroseconds,
                "WOT_PULL must run exactly twelve simulated seconds at the base step") &&
         expect(stock_first.front().current_gear == 3 &&
                    stock_first.front().vehicle_speed_meters_per_second == 15.0 &&
                    stock_first[200].accelerator_pedal_position == 1.0,
                "WOT_PULL must start rolling in third gear and apply full demand at two seconds") &&
         expect(stage1.manifold_pressure_kpa_absolute > stock.manifold_pressure_kpa_absolute &&
                    stage1.lambda < stock.lambda &&
                    !near(stage1.ignition_advance_degrees, stock.ignition_advance_degrees) &&
                    stage1.vehicle_speed_meters_per_second > stock.vehicle_speed_meters_per_second,
                "Stage 1 must alter MAP, lambda, ignition, and underlying vehicle response") &&
         expect(stock.current_gear == 3 && stage1.current_gear == 3 &&
                    stock.engine_speed_rpm >= 0.0 && stage1.engine_speed_rpm >= 0.0,
                "Both pulls must remain valid in their fixed synthetic third gear");
}

bool test_idle_profiles_remain_equivalent() {
  auto stock_configuration = make_default_idle_run_configuration();
  stock_configuration.duration = SimulationDuration{5'000'000};
  auto stage_configuration = stock_configuration;
  stage_configuration.calibration = CalibrationId::kStage1;
  VehicleSimulation stock{stock_configuration};
  VehicleSimulation stage1{stage_configuration};
  stock.run_to_completion();
  stage1.run_to_completion();
  return expect(stock.state() == stage1.state(),
                "Calibration must not create boost or alter established idle behavior");
}

}  // namespace

int main() {
  return test_table_lookup_and_clamping() && test_invalid_tables_rejected() &&
                 test_profiles_and_wot_schedule() &&
                 test_wot_profile_determinism_and_difference() &&
                 test_idle_profiles_remain_equivalent()
             ? 0
             : 1;
}
