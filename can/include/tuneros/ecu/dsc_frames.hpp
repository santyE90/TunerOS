#pragma once

#include <array>
#include <cstdint>

#include "tuneros/canbus/frame.hpp"
#include "tuneros/simulator/contracts.hpp"

namespace tuneros::ecu {

// TunerOS synthetic DSC identifiers and layouts. They are not BMW CAN definitions.
inline constexpr std::uint16_t kDscVehicleMotionFrameId = 0x520;
inline constexpr std::uint16_t kDscWheelSpeedsFrameId = 0x521;

inline constexpr std::uint8_t kDscVehicleMotionPayloadLength = 3;
inline constexpr std::uint8_t kDscWheelSpeedsPayloadLength = 8;

inline constexpr std::uint64_t kDscVehicleMotionPeriodMicroseconds = 20'000;
inline constexpr std::uint64_t kDscWheelSpeedsPeriodMicroseconds = 20'000;
inline constexpr double kDscSpeedScaleMetersPerSecond = 0.01;

[[nodiscard]] canbus::CanFrame make_dsc_vehicle_motion_frame(const simulator::VehicleState& state);
[[nodiscard]] canbus::CanFrame make_dsc_wheel_speeds_frame(const simulator::VehicleState& state);
[[nodiscard]] canbus::CanFrame make_dsc_wheel_speeds_frame(
    const simulator::VehicleState& state,
    const std::array<double, 4>& wheel_speeds_meters_per_second);

}  // namespace tuneros::ecu
