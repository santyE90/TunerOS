#pragma once

#include <array>
#include <cstdint>

namespace tuneros::canbus {

inline constexpr std::uint16_t kMaximumStandardArbitrationId = 0x7FF;
inline constexpr std::uint8_t kMaximumClassicCanPayloadLength = 8;

// Canonical application-level Classic CAN data frame. Payload bytes are opaque to the transport.
struct CanFrame {
  std::uint16_t arbitration_id{};
  std::uint8_t payload_length{};
  std::array<std::uint8_t, kMaximumClassicCanPayloadLength> payload{};
  std::uint64_t timestamp_microseconds{};

  friend constexpr bool operator==(const CanFrame&, const CanFrame&) = default;
};

[[nodiscard]] constexpr bool is_valid(const CanFrame& frame) noexcept {
  return frame.arbitration_id <= kMaximumStandardArbitrationId &&
         frame.payload_length <= kMaximumClassicCanPayloadLength;
}

}  // namespace tuneros::canbus
