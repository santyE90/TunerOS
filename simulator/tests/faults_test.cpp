#include "tuneros/simulator/faults.hpp"

#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <vector>

#include "tuneros/simulator/simulation.hpp"

namespace {

using namespace tuneros::simulator;

bool expect(bool condition, std::string_view message) {
  if (!condition) {
    std::cerr << message << '\n';
  }
  return condition;
}

bool test_configuration_and_exact_boundaries() {
  const FaultConfiguration fault{
      .id = FaultId::kChargingSystemFailure,
      .activation_time = {1'000'005},
      .deactivation_time = SimulationTimestamp{3'000'005},
  };
  const FaultConfigurations valid{fault};
  const FaultConfigurations duplicate{fault, fault};
  const FaultConfigurations invalid_interval{{
      .id = FaultId::kMapSensorBias,
      .activation_time = {10},
      .deactivation_time = SimulationTimestamp{10},
  }};
  const FaultConfiguration unknown_id{.id = static_cast<FaultId>(999)};

  return expect(are_valid(valid) && !are_valid(duplicate) && !are_valid(invalid_interval) &&
                    !is_valid(unknown_id),
                "Fault configuration must reject unknown/duplicate IDs and empty intervals") &&
         expect(!is_fault_active(fault, SimulationTimestamp{1'000'004}) &&
                    is_fault_active(fault, SimulationTimestamp{1'000'005}) &&
                    is_fault_active(fault, SimulationTimestamp{3'000'004}) &&
                    !is_fault_active(fault, SimulationTimestamp{3'000'005}),
                "Fault interval must be [activation, deactivation)");
}

bool test_fault_aware_sensor_observation() {
  VehicleState state{
      .timestamp = {1'000'000},
      .vehicle_speed_meters_per_second = 10.0,
      .manifold_pressure_kpa_absolute = 80.0,
  };
  const FaultConfigurations faults{
      {.id = FaultId::kMapSensorBias, .activation_time = {1'000'000}},
      {.id = FaultId::kFrontLeftWheelSpeedSensorBias,
       .activation_time = {1'000'000},
       .deactivation_time = SimulationTimestamp{2'000'000}},
  };
  state.timestamp = SimulationTimestamp{999'999};
  const auto before = observe_sensors(state, faults);
  if (!expect(before.dme_state.manifold_pressure_kpa_absolute == 80.0 &&
                  before.wheel_speeds_meters_per_second ==
                      std::array<double, 4>{10.0, 10.0, 10.0, 10.0},
              "Sensor observations must remain normal before activation")) {
    return false;
  }

  state.timestamp = SimulationTimestamp{1'000'000};
  const auto active = observe_sensors(state, faults);
  if (!expect(state.manifold_pressure_kpa_absolute == 80.0 &&
                  state.vehicle_speed_meters_per_second == 10.0,
              "Sensor faults must not mutate canonical physical truth") ||
      !expect(active.dme_state.manifold_pressure_kpa_absolute == 300.0,
              "MAP observation must receive the fixed synthetic bias") ||
      !expect(
          active.wheel_speeds_meters_per_second == std::array<double, 4>{15.0, 10.0, 10.0, 10.0},
          "Only the front-left wheel observation may be biased")) {
    return false;
  }

  state.timestamp = SimulationTimestamp{2'000'000};
  const auto cleared = observe_sensors(state, faults);
  return expect(
      cleared.wheel_speeds_meters_per_second == std::array<double, 4>{10.0, 10.0, 10.0, 10.0} &&
          cleared.dme_state.manifold_pressure_kpa_absolute == 300.0,
      "Each sensor fault must independently respect its deactivation boundary");
}

bool test_physical_fault_evolution_and_recovery() {
  auto baseline_configuration = make_default_idle_run_configuration();
  baseline_configuration.duration = SimulationDuration{35'000'000};
  auto faulty_configuration = baseline_configuration;
  faulty_configuration.faults = {
      {.id = FaultId::kCoolingSystemDegradation,
       .activation_time = {1'000'000},
       .deactivation_time = SimulationTimestamp{30'000'000}},
      {.id = FaultId::kChargingSystemFailure,
       .activation_time = {1'000'000},
       .deactivation_time = SimulationTimestamp{6'000'000}},
  };
  VehicleSimulation baseline{baseline_configuration};
  VehicleSimulation faulty{faulty_configuration};

  baseline.advance_ticks(99);
  faulty.advance_ticks(99);
  if (!expect(baseline.state() == faulty.state(),
              "No fault effect may occur before the exact activation boundary")) {
    return false;
  }
  baseline.tick();
  faulty.tick();
  if (!expect(faulty.state().coolant_temperature_celsius >
                      baseline.state().coolant_temperature_celsius &&
                  faulty.state().battery_voltage_volts < baseline.state().battery_voltage_volts,
              "Physical fault dynamics must begin at the activation boundary")) {
    return false;
  }

  faulty.advance_ticks(499);
  const double low_voltage = faulty.state().battery_voltage_volts;
  if (!expect(low_voltage < 12.5,
              "Charging failure must evolve below the existing diagnostic threshold")) {
    return false;
  }
  faulty.tick();
  if (!expect(faulty.state().timestamp.microseconds == 6'000'000 &&
                  faulty.state().battery_voltage_volts > low_voltage,
              "Charging voltage must naturally recover at the deactivation boundary")) {
    return false;
  }

  faulty.advance_ticks(2'399);
  const double hot_coolant = faulty.state().coolant_temperature_celsius;
  if (!expect(faulty.state().timestamp.microseconds == 29'990'000 && hot_coolant > 115.0,
              "Cooling degradation must evolve through the diagnostic-relevant region")) {
    return false;
  }
  faulty.tick();
  return expect(faulty.state().timestamp.microseconds == 30'000'000 &&
                    faulty.state().coolant_temperature_celsius < hot_coolant,
                "Coolant must naturally trend toward the normal model at deactivation");
}

bool test_reset_reproduces_fault_run_exactly() {
  auto configuration = make_default_city_run_configuration();
  configuration.duration = SimulationDuration{8'000'000};
  configuration.faults = {
      {.id = FaultId::kChargingSystemFailure, .activation_time = {1'000'005}},
  };
  VehicleSimulation simulation{configuration};
  std::vector<VehicleState> first;
  while (simulation.tick()) {
    first.push_back(simulation.state());
  }
  simulation.reset();
  std::vector<VehicleState> second;
  while (simulation.tick()) {
    second.push_back(simulation.state());
  }
  return expect(first == second && first.front().timestamp.microseconds == 10'000 &&
                    first.back().timestamp.microseconds == 8'000'000,
                "Reset must reproduce every fault-derived VehicleState exactly");
}

bool test_invalid_simulation_fault_configuration_rejected() {
  auto configuration = make_default_idle_run_configuration();
  configuration.faults = {
      {.id = FaultId::kChargingSystemFailure,
       .activation_time = {2},
       .deactivation_time = SimulationTimestamp{1}},
  };
  try {
    [[maybe_unused]] const VehicleSimulation invalid{configuration};
    return expect(false, "VehicleSimulation must reject an invalid fault interval");
  } catch (const std::invalid_argument&) {
    return true;
  }
}

}  // namespace

int main() {
  return test_configuration_and_exact_boundaries() && test_fault_aware_sensor_observation() &&
                 test_physical_fault_evolution_and_recovery() &&
                 test_reset_reproduces_fault_run_exactly() &&
                 test_invalid_simulation_fault_configuration_rejected()
             ? 0
             : 1;
}
