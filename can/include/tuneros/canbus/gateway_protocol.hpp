#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

#include "tuneros/canbus/frame.hpp"

namespace tuneros::canbus {

inline constexpr std::array<std::uint8_t, 4> kGatewayMagic{'T', 'N', 'C', 'R'};
inline constexpr std::uint8_t kGatewayProtocolVersion = 1;
inline constexpr std::size_t kGatewayHeaderSize = 8;
inline constexpr std::size_t kGatewayRecordSize = 19;
inline constexpr std::uint16_t kDefaultGatewayPort = 45800;

using GatewayHeader = std::array<std::uint8_t, kGatewayHeaderSize>;
using GatewayRecord = std::array<std::uint8_t, kGatewayRecordSize>;

[[nodiscard]] constexpr GatewayHeader make_gateway_header() noexcept {
  return {kGatewayMagic[0],
          kGatewayMagic[1],
          kGatewayMagic[2],
          kGatewayMagic[3],
          kGatewayProtocolVersion,
          0,
          0,
          0};
}

// Serializes metadata in network byte order. CAN payload bytes retain their existing order.
// The fixed payload area is zero-filled beyond the frame DLC.
[[nodiscard]] GatewayRecord serialize_gateway_record(const CanFrame& frame);

}  // namespace tuneros::canbus
