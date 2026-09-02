#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string_view>
#include <vector>

#include "tuneros/canbus/in_memory_transport.hpp"
#include "tuneros/ecu/dsc_frames.hpp"
#include "tuneros/ecu/simulated_dsc.hpp"
#include "tuneros/simulator/contracts.hpp"

namespace {

using namespace tuneros;

bool expect(bool condition, std::string_view message) {
  if (!condition) {
    std::cerr << message << '\n';
  }
  return condition;
}

simulator::VehicleState state_at(double speed, std::int8_t gear,
                                 std::uint64_t timestamp = 123'000) {
  return {
      .timestamp = {timestamp},
      .vehicle_speed_meters_per_second = speed,
      .current_gear = gear,
  };
}

bool test_exact_motion_and_wheel_layouts() {
  const auto state = state_at(12.34, 3);
  const auto motion = ecu::make_dsc_vehicle_motion_frame(state);
  const auto wheels = ecu::make_dsc_wheel_speeds_frame(state);
  const std::array<std::uint8_t, 8> expected_motion{0xD2, 0x04, 0x03, 0, 0, 0, 0, 0};
  const std::array<std::uint8_t, 8> expected_wheels{0xD2, 0x04, 0xD2, 0x04, 0xD2, 0x04, 0xD2, 0x04};
  return expect(motion.arbitration_id == ecu::kDscVehicleMotionFrameId &&
                    motion.payload_length == ecu::kDscVehicleMotionPayloadLength &&
                    motion.payload == expected_motion && motion.timestamp_microseconds == 123'000,
                "DSC motion frame must match the exact synthetic little-endian layout") &&
         expect(wheels.arbitration_id == ecu::kDscWheelSpeedsFrameId &&
                    wheels.payload_length == ecu::kDscWheelSpeedsPayloadLength &&
                    wheels.payload == expected_wheels && wheels.timestamp_microseconds == 123'000,
                "All four synthetic wheel speeds must exactly equal vehicle speed");
}

bool test_zero_saturation_and_non_finite_rejection() {
  const auto zero_motion = ecu::make_dsc_vehicle_motion_frame(state_at(0.0, 0));
  const auto zero_wheels = ecu::make_dsc_wheel_speeds_frame(state_at(0.0, 0));
  if (!expect(zero_motion.payload == std::array<std::uint8_t, 8>{} &&
                  zero_wheels.payload == std::array<std::uint8_t, 8>{},
              "Stationary DSC frames must contain exact zero speed and neutral bytes")) {
    return false;
  }

  const auto low = ecu::make_dsc_vehicle_motion_frame(state_at(-1.0, 0));
  const auto high = ecu::make_dsc_wheel_speeds_frame(state_at(1'000.0, 1));
  if (!expect(low.payload[0] == 0 && low.payload[1] == 0 && high.payload[0] == 0xFF &&
                  high.payload[1] == 0xFF && high.payload[6] == 0xFF && high.payload[7] == 0xFF,
              "DSC speeds must saturate at unsigned 16-bit endpoints without wrapping")) {
    return false;
  }

  try {
    [[maybe_unused]] const auto invalid =
        ecu::make_dsc_vehicle_motion_frame(state_at(std::numeric_limits<double>::infinity(), 1));
    return expect(false, "Non-finite DSC speed must be rejected");
  } catch (const std::invalid_argument&) {
    return true;
  }
}

bool test_scheduler_and_reset() {
  ecu::SimulatedDsc dsc;
  canbus::InMemoryTransport transport;
  for (const auto timestamp : {0ULL, 10'000ULL, 20'000ULL, 40'000ULL}) {
    dsc.observe_and_publish(state_at(5.0, 1, timestamp), transport);
  }
  const auto first = transport.drain();
  if (!expect(first.size() == 6 && first[0].timestamp_microseconds == 0 &&
                  first[1].timestamp_microseconds == 0 &&
                  first[2].timestamp_microseconds == 20'000 &&
                  first[4].timestamp_microseconds == 40'000,
              "DSC must publish both frames at t=0 and exact 50 Hz due timestamps")) {
    return false;
  }

  dsc.reset();
  dsc.observe_and_publish(state_at(5.0, 1, 0), transport);
  return expect(transport.drain() == std::vector<canbus::CanFrame>{first[0], first[1]},
                "DSC reset must exactly restore initial publication state");
}

bool test_non_divisible_schedule_and_validation() {
  ecu::SimulatedDsc dsc;
  canbus::InMemoryTransport transport;
  for (const auto timestamp : {0ULL, 15'000ULL, 30'000ULL, 45'000ULL}) {
    dsc.observe_and_publish(state_at(5.0, 1, timestamp), transport);
  }
  const auto frames = transport.drain();
  if (!expect(frames.size() == 6 && frames[2].timestamp_microseconds == 30'000 &&
                  frames[4].timestamp_microseconds == 45'000,
              "A 15 ms observer step must deterministically cross DSC due timestamps")) {
    return false;
  }

  try {
    [[maybe_unused]] const ecu::SimulatedDsc invalid{
        ecu::DscPublicationSchedule{.vehicle_motion_period_microseconds = 0}};
    return expect(false, "A zero DSC publication period must be rejected");
  } catch (const std::invalid_argument&) {
    return true;
  }
}

}  // namespace

int main() {
  return test_exact_motion_and_wheel_layouts() && test_zero_saturation_and_non_finite_rejection() &&
                 test_scheduler_and_reset() && test_non_divisible_schedule_and_validation()
             ? 0
             : 1;
}
