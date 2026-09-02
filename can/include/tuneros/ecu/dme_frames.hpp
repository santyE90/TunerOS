#pragma once

#include <cstdint>

#include "tuneros/canbus/frame.hpp"
#include "tuneros/simulator/contracts.hpp"

namespace tuneros::ecu {

// TunerOS synthetic identifiers and layouts. They are not BMW CAN definitions.
inline constexpr std::uint16_t kDmeFastEngineFrameId = 0x500;
inline constexpr std::uint16_t kDmeAirLoadFrameId = 0x501;
inline constexpr std::uint16_t kDmeThermalElectricalFrameId = 0x502;

inline constexpr std::uint8_t kDmeFastEnginePayloadLength = 5;
inline constexpr std::uint8_t kDmeAirLoadPayloadLength = 4;
inline constexpr std::uint8_t kDmeThermalElectricalPayloadLength = 7;

inline constexpr std::uint64_t kDmeFastEnginePeriodMicroseconds = 10'000;
inline constexpr std::uint64_t kDmeAirLoadPeriodMicroseconds = 20'000;
inline constexpr std::uint64_t kDmeThermalElectricalPeriodMicroseconds = 100'000;

[[nodiscard]] canbus::CanFrame make_dme_fast_engine_frame(const simulator::VehicleState& state);
[[nodiscard]] canbus::CanFrame make_dme_air_load_frame(const simulator::VehicleState& state);
[[nodiscard]] canbus::CanFrame make_dme_thermal_electrical_frame(
    const simulator::VehicleState& state);

}  // namespace tuneros::ecu
