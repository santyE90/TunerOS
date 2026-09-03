#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <vector>

#include "tuneros/canbus/frame.hpp"
#include "tuneros/ecu/dme_frames.hpp"
#include "tuneros/ecu/dsc_frames.hpp"
#include "tuneros/ecu/simulated_dme.hpp"
#include "tuneros/ecu/vehicle_network_simulation.hpp"
#include "tuneros/simulator/simulation.hpp"

namespace {

using namespace tuneros;

bool expect(bool condition, std::string_view message) {
  if (!condition) {
    std::cerr << message << '\n';
  }
  return condition;
}

std::size_t count_id(const std::vector<canbus::CanFrame>& frames, std::uint16_t id) {
  return static_cast<std::size_t>(
      std::count_if(frames.begin(), frames.end(),
                    [id](const auto& frame) { return frame.arbitration_id == id; }));
}

const canbus::CanFrame* find_frame(const std::vector<canbus::CanFrame>& frames, std::uint16_t id,
                                   std::uint64_t timestamp) {
  const auto found = std::find_if(frames.begin(), frames.end(), [=](const auto& frame) {
    return frame.arbitration_id == id && frame.timestamp_microseconds == timestamp;
  });
  return found == frames.end() ? nullptr : &*found;
}

std::uint16_t little_endian_u16(const canbus::CanFrame& frame, std::size_t offset = 0) {
  return static_cast<std::uint16_t>(frame.payload[offset]) |
         static_cast<std::uint16_t>(static_cast<std::uint16_t>(frame.payload[offset + 1]) << 8U);
}

bool has_ascending_same_timestamp_order(const std::vector<canbus::CanFrame>& frames) {
  for (std::size_t index = 1; index < frames.size(); ++index) {
    if (frames[index - 1].timestamp_microseconds == frames[index].timestamp_microseconds &&
        frames[index - 1].arbitration_id >= frames[index].arbitration_id) {
      return false;
    }
  }
  return true;
}

bool test_exact_default_rates_and_ordering() {
  auto configuration = simulator::make_default_idle_run_configuration();
  configuration.duration = simulator::SimulationDuration{1'000'000};
  ecu::VehicleNetworkSimulation network{configuration};

  if (!expect(network.transport().size() == 5,
              "Construction must publish all five DME and DSC snapshots at t=0")) {
    return false;
  }
  network.run_to_completion();
  const auto frames = network.transport().drain();

  return expect(count_id(frames, ecu::kDmeFastEngineFrameId) == 101,
                "Inclusive one-second run must contain 101 fast frames") &&
         expect(count_id(frames, ecu::kDmeAirLoadFrameId) == 51,
                "Inclusive one-second run must contain 51 air/load frames") &&
         expect(count_id(frames, ecu::kDmeThermalElectricalFrameId) == 11,
                "Inclusive one-second run must contain 11 thermal/electrical frames") &&
         expect(count_id(frames, ecu::kDscVehicleMotionFrameId) == 51,
                "Inclusive one-second run must contain 51 DSC motion frames") &&
         expect(count_id(frames, ecu::kDscWheelSpeedsFrameId) == 51,
                "Inclusive one-second run must contain 51 DSC wheel-speed frames") &&
         expect(frames.size() == 265 && has_ascending_same_timestamp_order(frames),
                "Combined count and global same-timestamp CAN-ID order must be exact") &&
         expect(std::vector<std::uint16_t>{frames[0].arbitration_id, frames[1].arbitration_id,
                                           frames[2].arbitration_id, frames[3].arbitration_id,
                                           frames[4].arbitration_id} ==
                    std::vector<std::uint16_t>{0x500, 0x501, 0x502, 0x520, 0x521},
                "The t=0 DME and DSC sequence must be globally ordered by CAN ID") &&
         expect(frames.front().timestamp_microseconds == 0 &&
                    frames.back().timestamp_microseconds == 1'000'000,
                "Frame timestamps must span the inclusive simulation boundary exactly");
}

bool test_non_divisible_and_undersampled_steps() {
  auto configuration = simulator::make_default_idle_run_configuration();
  configuration.duration = simulator::SimulationDuration{1'050'000};
  configuration.fixed_step = simulator::SimulationDuration{15'000};
  ecu::VehicleNetworkSimulation network{configuration};
  network.run_to_completion();
  auto frames = network.transport().drain();
  if (!expect(count_id(frames, ecu::kDmeFastEngineFrameId) == 71 &&
                  count_id(frames, ecu::kDmeAirLoadFrameId) == 53 &&
                  count_id(frames, ecu::kDmeThermalElectricalFrameId) == 11 &&
                  count_id(frames, ecu::kDscVehicleMotionFrameId) == 53 &&
                  count_id(frames, ecu::kDscWheelSpeedsFrameId) == 53 && frames.size() == 241 &&
                  has_ascending_same_timestamp_order(frames),
              "A 15 ms step must deterministically publish and globally order both ECUs")) {
    return false;
  }
  for (const auto& frame : frames) {
    if (!expect(frame.timestamp_microseconds % 15'000 == 0,
                "Non-divisible schedules must timestamp the state actually observed")) {
      return false;
    }
  }

  configuration.duration = simulator::SimulationDuration{1'000'000};
  configuration.fixed_step = simulator::SimulationDuration{25'000};
  ecu::VehicleNetworkSimulation undersampled{configuration};
  undersampled.run_to_completion();
  frames = undersampled.transport().drain();
  return expect(count_id(frames, ecu::kDmeFastEngineFrameId) == 41 &&
                    count_id(frames, ecu::kDmeAirLoadFrameId) == 41 &&
                    count_id(frames, ecu::kDmeThermalElectricalFrameId) == 11 &&
                    count_id(frames, ecu::kDscVehicleMotionFrameId) == 41 &&
                    count_id(frames, ecu::kDscWheelSpeedsFrameId) == 41,
                "A large step must emit at most one frame type per observed VehicleState");
}

bool test_city_changes_binary_frames_and_replays() {
  auto configuration = simulator::make_default_city_run_configuration();
  ecu::VehicleNetworkSimulation network{configuration};
  network.run_to_completion();
  const auto& queued_first_run = network.transport().queued_frames();
  const std::vector<canbus::CanFrame> first_run(queued_first_run.begin(), queued_first_run.end());
  if (!expect(first_run.size() == 27'305,
              "Default CITY must produce the exact inclusive combined ECU frame count")) {
    return false;
  }

  const auto* initial_fast = find_frame(first_run, ecu::kDmeFastEngineFrameId, 0);
  const auto* initial_air = find_frame(first_run, ecu::kDmeAirLoadFrameId, 0);
  const auto* initial_thermal = find_frame(first_run, ecu::kDmeThermalElectricalFrameId, 0);
  const auto* initial_motion = find_frame(first_run, ecu::kDscVehicleMotionFrameId, 0);
  const auto* initial_wheels = find_frame(first_run, ecu::kDscWheelSpeedsFrameId, 0);
  if (!expect(initial_fast != nullptr && initial_air != nullptr && initial_thermal != nullptr &&
                  initial_motion != nullptr && initial_wheels != nullptr,
              "CITY must publish all initial DME and DSC snapshots")) {
    return false;
  }

  const bool rpm_changed = std::any_of(first_run.begin(), first_run.end(), [&](const auto& frame) {
    return frame.arbitration_id == ecu::kDmeFastEngineFrameId &&
           (frame.payload[0] != initial_fast->payload[0] ||
            frame.payload[1] != initial_fast->payload[1]);
  });
  const bool throttle_load_changed =
      std::any_of(first_run.begin(), first_run.end(), [&](const auto& frame) {
        return frame.arbitration_id == ecu::kDmeFastEngineFrameId &&
               (frame.payload[2] != initial_fast->payload[2] ||
                frame.payload[3] != initial_fast->payload[3]);
      });
  const std::uint16_t initial_map_raw =
      static_cast<std::uint16_t>(initial_air->payload[0]) |
      static_cast<std::uint16_t>(static_cast<std::uint16_t>(initial_air->payload[1]) << 8U);
  const bool map_moved_toward_ambient =
      std::any_of(first_run.begin(), first_run.end(), [&](const auto& frame) {
        if (frame.arbitration_id != ecu::kDmeAirLoadFrameId) {
          return false;
        }
        const std::uint16_t map_raw =
            static_cast<std::uint16_t>(frame.payload[0]) |
            static_cast<std::uint16_t>(static_cast<std::uint16_t>(frame.payload[1]) << 8U);
        return map_raw > initial_map_raw && (frame.payload[2] != initial_air->payload[2] ||
                                             frame.payload[3] != initial_air->payload[3]);
      });
  const bool thermal_changed =
      std::any_of(first_run.begin(), first_run.end(), [&](const auto& frame) {
        return frame.arbitration_id == ecu::kDmeThermalElectricalFrameId &&
               frame.payload != initial_thermal->payload;
      });
  if (!expect(rpm_changed && throttle_load_changed && map_moved_toward_ambient && thermal_changed,
              "CITY RPM, throttle/load/MAP, and thermal bytes must evolve from VehicleState")) {
    return false;
  }

  const bool motion_changed =
      std::any_of(first_run.begin(), first_run.end(), [&](const auto& frame) {
        return frame.arbitration_id == ecu::kDscVehicleMotionFrameId &&
               frame.payload != initial_motion->payload;
      });
  const bool wheels_changed =
      std::any_of(first_run.begin(), first_run.end(), [&](const auto& frame) {
        return frame.arbitration_id == ecu::kDscWheelSpeedsFrameId &&
               frame.payload != initial_wheels->payload;
      });
  const auto* intermediate_stop = find_frame(first_run, ecu::kDscVehicleMotionFrameId, 54'980'000);
  const auto* final_stop = find_frame(first_run, ecu::kDscVehicleMotionFrameId, 105'000'000);
  const auto* before_deceleration =
      find_frame(first_run, ecu::kDscVehicleMotionFrameId, 32'000'000);
  const auto* during_deceleration =
      find_frame(first_run, ecu::kDscVehicleMotionFrameId, 44'000'000);
  if (!expect(motion_changed && wheels_changed && intermediate_stop != nullptr &&
                  intermediate_stop->payload[0] == 0 && intermediate_stop->payload[1] == 0 &&
                  intermediate_stop->payload[2] == 0 && final_stop != nullptr &&
                  final_stop->payload[0] == 0 && final_stop->payload[1] == 0 &&
                  final_stop->payload[2] == 0 && before_deceleration != nullptr &&
                  during_deceleration != nullptr &&
                  little_endian_u16(*during_deceleration) < little_endian_u16(*before_deceleration),
              "CITY DSC speed must rise, decline, and encode exact zero at both stops")) {
    return false;
  }

  for (const auto& frame : first_run) {
    if (frame.arbitration_id == ecu::kDscWheelSpeedsFrameId &&
        !expect(frame.payload[0] == frame.payload[2] && frame.payload[0] == frame.payload[4] &&
                    frame.payload[0] == frame.payload[6] && frame.payload[1] == frame.payload[3] &&
                    frame.payload[1] == frame.payload[5] && frame.payload[1] == frame.payload[7],
                "All four Phase 3A wheel speeds must have identical quantized bytes")) {
      return false;
    }
  }

  network.reset();
  if (!expect(network.transport().size() == 5,
              "Network reset must clear old traffic and republish all five t=0 snapshots")) {
    return false;
  }
  network.run_to_completion();
  const auto replay = network.transport().drain();
  return expect(first_run == replay,
                "CITY reset and replay must reproduce the complete exact CAN sequence");
}

bool test_cold_start_publication() {
  auto configuration = simulator::make_default_cold_start_run_configuration();
  configuration.duration = simulator::SimulationDuration{2'000'000};
  ecu::VehicleNetworkSimulation network{configuration};
  network.run_to_completion();
  const auto frames = network.transport().drain();

  const auto* initial_fast = find_frame(frames, ecu::kDmeFastEngineFrameId, 0);
  const auto* started_fast = find_frame(frames, ecu::kDmeFastEngineFrameId, 1'000'000);
  const auto* initial_thermal = find_frame(frames, ecu::kDmeThermalElectricalFrameId, 0);
  const auto* later_thermal = find_frame(frames, ecu::kDmeThermalElectricalFrameId, 2'000'000);
  const auto dsc_motion_count = count_id(frames, ecu::kDscVehicleMotionFrameId);
  const bool dsc_is_stationary = std::all_of(frames.begin(), frames.end(), [](const auto& frame) {
    return frame.arbitration_id != ecu::kDscVehicleMotionFrameId ||
           (frame.payload[0] == 0 && frame.payload[1] == 0 && frame.payload[2] == 0);
  });
  return expect(initial_fast != nullptr && initial_fast->payload[0] == 0 &&
                    initial_fast->payload[1] == 0 && initial_fast->payload[4] == 0,
                "COLD_START must initially publish zero RPM and engine-off") &&
         expect(started_fast != nullptr &&
                    (started_fast->payload[0] != 0 || started_fast->payload[1] != 0) &&
                    started_fast->payload[4] == 1,
                "COLD_START must publish running state and rising RPM at one second") &&
         expect(initial_thermal != nullptr && later_thermal != nullptr &&
                    initial_thermal->payload != later_thermal->payload,
                "COLD_START electrical/thermal publication must evolve with vehicle state") &&
         expect(dsc_motion_count == 101 && dsc_is_stationary,
                "COLD_START DSC must keep publishing zero-speed neutral motion at 50 Hz");
}

bool test_wot_calibration_changes_exact_raw_can() {
  auto stock_configuration = simulator::make_default_wot_pull_run_configuration();
  auto stage_configuration =
      simulator::make_default_wot_pull_run_configuration({}, simulator::CalibrationId::kStage1);
  ecu::VehicleNetworkSimulation stock{stock_configuration};
  ecu::VehicleNetworkSimulation stage1{stage_configuration};
  stock.run_to_completion();
  stage1.run_to_completion();
  const auto stock_first = stock.transport().drain();
  const auto stage_first = stage1.transport().drain();
  stock.reset();
  stage1.reset();
  stock.run_to_completion();
  stage1.run_to_completion();
  const auto stock_second = stock.transport().drain();
  const auto stage_second = stage1.transport().drain();
  return expect(stock_first == stock_second && stage_first == stage_second,
                "Stock and Stage 1 WOT raw CAN sequences must each reproduce exactly") &&
         expect(stock_first != stage_first,
                "Calibration selection must change downstream WOT raw CAN evidence") &&
         expect(count_id(stock_first, ecu::kDmeCombustionObservationFrameId) == 601 &&
                    count_id(stage_first, ecu::kDmeCombustionObservationFrameId) == 601,
                "Each inclusive WOT pull must publish 601 combustion observations") &&
         expect(stock_first.front().arbitration_id == 0x500 &&
                    find_frame(stock_first, 0x503, 0) != nullptr,
                "WOT initial publication must include the additive DME observation frame");
}

bool test_invalid_schedule_rejected() {
  try {
    [[maybe_unused]] const ecu::SimulatedDme invalid{
        ecu::DmePublicationSchedule{.fast_engine_period_microseconds = 0}};
    return expect(false, "A zero DME publication period must be rejected");
  } catch (const std::invalid_argument&) {
  }
  try {
    [[maybe_unused]] const ecu::VehicleNetworkSimulation invalid{
        simulator::make_default_idle_run_configuration(),
        {},
        ecu::DscPublicationSchedule{.wheel_speeds_period_microseconds = 0}};
    return expect(false, "A zero DSC network publication period must be rejected");
  } catch (const std::invalid_argument&) {
  }
  return true;
}

}  // namespace

int main() {
  if (!test_exact_default_rates_and_ordering() || !test_non_divisible_and_undersampled_steps() ||
      !test_city_changes_binary_frames_and_replays() || !test_cold_start_publication() ||
      !test_wot_calibration_changes_exact_raw_can() || !test_invalid_schedule_rejected()) {
    return 1;
  }
  return 0;
}
