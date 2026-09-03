#include <algorithm>
#include <cstdint>
#include <iostream>
#include <string_view>
#include <vector>

#include "tuneros/canbus/frame.hpp"
#include "tuneros/ecu/dme_frames.hpp"
#include "tuneros/ecu/dsc_frames.hpp"
#include "tuneros/ecu/vehicle_network_simulation.hpp"
#include "tuneros/simulator/faults.hpp"
#include "tuneros/simulator/simulation.hpp"

namespace {

using namespace tuneros;

bool expect(bool condition, std::string_view message) {
  if (!condition) {
    std::cerr << message << '\n';
  }
  return condition;
}

const canbus::CanFrame* find_frame(const std::vector<canbus::CanFrame>& frames, std::uint16_t id,
                                   std::uint64_t timestamp) {
  const auto found = std::find_if(frames.begin(), frames.end(), [=](const auto& frame) {
    return frame.arbitration_id == id && frame.timestamp_microseconds == timestamp;
  });
  return found == frames.end() ? nullptr : &*found;
}

std::vector<canbus::CanFrame> run_city(simulator::SimulationDuration duration,
                                       simulator::FaultConfigurations faults = {}) {
  auto configuration = simulator::make_default_city_run_configuration();
  configuration.duration = duration;
  configuration.faults = std::move(faults);
  ecu::VehicleNetworkSimulation network{configuration};
  network.run_to_completion();
  return network.transport().drain();
}

bool test_system_faults_change_only_existing_thermal_electrical_values() {
  const auto baseline = run_city({30'000'000});
  const auto cooling = run_city({30'000'000}, {{.id = simulator::FaultId::kCoolingSystemDegradation,
                                                .activation_time = {1'000'000}}});
  const auto charging = run_city({8'000'000}, {{.id = simulator::FaultId::kChargingSystemFailure,
                                                .activation_time = {1'000'000}}});
  const auto charging_baseline = run_city({8'000'000});
  const auto* baseline_thermal =
      find_frame(baseline, ecu::kDmeThermalElectricalFrameId, 30'000'000);
  const auto* cooling_thermal = find_frame(cooling, ecu::kDmeThermalElectricalFrameId, 30'000'000);
  const auto* baseline_charging =
      find_frame(charging_baseline, ecu::kDmeThermalElectricalFrameId, 8'000'000);
  const auto* failed_charging = find_frame(charging, ecu::kDmeThermalElectricalFrameId, 8'000'000);

  return expect(baseline.size() == cooling.size() && charging.size() == charging_baseline.size(),
                "Faults must not change CAN publication counts") &&
         expect(baseline_thermal != nullptr && cooling_thermal != nullptr &&
                    (cooling_thermal->payload[0] != baseline_thermal->payload[0] ||
                     cooling_thermal->payload[1] != baseline_thermal->payload[1]) &&
                    std::equal(cooling_thermal->payload.begin() + 2, cooling_thermal->payload.end(),
                               baseline_thermal->payload.begin() + 2),
                "Cooling degradation must change only coolant bytes in existing 0x502") &&
         expect(
             baseline_charging != nullptr && failed_charging != nullptr &&
                 failed_charging->payload[6] < baseline_charging->payload[6] &&
                 std::equal(failed_charging->payload.begin(), failed_charging->payload.begin() + 6,
                            baseline_charging->payload.begin()),
             "Charging failure must change only battery voltage in existing 0x502");
}

bool test_map_sensor_bias_changes_observation_not_vehicle_truth() {
  auto configuration = simulator::make_default_city_run_configuration();
  configuration.duration = {2'000'000};
  configuration.faults = {{
      .id = simulator::FaultId::kMapSensorBias,
      .activation_time = {1'000'000},
      .deactivation_time = simulator::SimulationTimestamp{2'000'000},
  }};
  ecu::VehicleNetworkSimulation network{configuration};
  network.run_to_completion();
  const double physical_map = network.vehicle_simulation().state().manifold_pressure_kpa_absolute;
  const auto frames = network.transport().drain();
  const auto* biased = find_frame(frames, ecu::kDmeAirLoadFrameId, 1'000'000);
  const auto* restored = find_frame(frames, ecu::kDmeAirLoadFrameId, 2'000'000);
  const auto baseline = run_city({2'000'000});
  const auto* baseline_biased_time = find_frame(baseline, ecu::kDmeAirLoadFrameId, 1'000'000);
  const auto* baseline_restored_time = find_frame(baseline, ecu::kDmeAirLoadFrameId, 2'000'000);

  return expect(physical_map < 250.0,
                "MAP sensor bias must leave canonical manifold pressure plausible") &&
         expect(biased != nullptr && baseline_biased_time != nullptr &&
                    biased->payload[0] != baseline_biased_time->payload[0],
                "MAP bias must alter the existing 0x501 observed MAP bytes") &&
         expect(restored != nullptr && baseline_restored_time != nullptr &&
                    restored->payload == baseline_restored_time->payload,
                "MAP observation must exactly return to normal at deactivation");
}

bool test_front_left_wheel_bias_preserves_vehicle_and_other_wheels() {
  auto configuration = simulator::make_default_city_run_configuration();
  configuration.duration = {2'000'000};
  configuration.faults = {{
      .id = simulator::FaultId::kFrontLeftWheelSpeedSensorBias,
      .activation_time = {1'000'000},
      .deactivation_time = simulator::SimulationTimestamp{2'000'000},
  }};
  ecu::VehicleNetworkSimulation network{configuration};
  network.run_to_completion();
  const auto frames = network.transport().drain();
  const auto baseline = run_city({2'000'000});
  const auto* motion = find_frame(frames, ecu::kDscVehicleMotionFrameId, 1'000'000);
  const auto* baseline_motion = find_frame(baseline, ecu::kDscVehicleMotionFrameId, 1'000'000);
  const auto* wheels = find_frame(frames, ecu::kDscWheelSpeedsFrameId, 1'000'000);
  const auto* baseline_wheels = find_frame(baseline, ecu::kDscWheelSpeedsFrameId, 1'000'000);
  const auto* restored = find_frame(frames, ecu::kDscWheelSpeedsFrameId, 2'000'000);
  const auto* baseline_restored = find_frame(baseline, ecu::kDscWheelSpeedsFrameId, 2'000'000);

  return expect(motion != nullptr && baseline_motion != nullptr &&
                    motion->payload == baseline_motion->payload,
                "Wheel sensor fault must not change canonical 0x520 vehicle motion") &&
         expect(wheels != nullptr && baseline_wheels != nullptr &&
                    (wheels->payload[0] != baseline_wheels->payload[0] ||
                     wheels->payload[1] != baseline_wheels->payload[1]) &&
                    std::equal(wheels->payload.begin() + 2, wheels->payload.end(),
                               baseline_wheels->payload.begin() + 2),
                "Only front-left bytes may change in existing 0x521") &&
         expect(restored != nullptr && baseline_restored != nullptr &&
                    restored->payload == baseline_restored->payload,
                "All wheel observations must return to exact equality at deactivation");
}

bool test_fault_network_reset_is_exact() {
  auto configuration = simulator::make_default_city_run_configuration();
  configuration.duration = {8'000'000};
  configuration.faults = {
      {.id = simulator::FaultId::kCoolingSystemDegradation, .activation_time = {500'005}},
      {.id = simulator::FaultId::kChargingSystemFailure, .activation_time = {1'000'005}},
      {.id = simulator::FaultId::kMapSensorBias, .activation_time = {1'500'005}},
      {.id = simulator::FaultId::kFrontLeftWheelSpeedSensorBias, .activation_time = {2'000'005}},
  };
  ecu::VehicleNetworkSimulation network{configuration};
  network.run_to_completion();
  const auto first = network.transport().drain();
  network.reset();
  network.run_to_completion();
  const auto second = network.transport().drain();
  return expect(first == second, "Reset must reproduce the exact multi-fault raw CAN sequence");
}

}  // namespace

int main() {
  return test_system_faults_change_only_existing_thermal_electrical_values() &&
                 test_map_sensor_bias_changes_observation_not_vehicle_truth() &&
                 test_front_left_wheel_bias_preserves_vehicle_and_other_wheels() &&
                 test_fault_network_reset_is_exact()
             ? 0
             : 1;
}
