#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace tuneros::ecu::detail {

[[nodiscard]] inline std::uint16_t encode_scaled_u16(double value, double scale, double offset) {
  if (!std::isfinite(value)) {
    throw std::invalid_argument("cannot encode a non-finite CAN signal");
  }
  const double raw = std::round((value - offset) / scale);
  return static_cast<std::uint16_t>(
      std::clamp(raw, 0.0, static_cast<double>(std::numeric_limits<std::uint16_t>::max())));
}

[[nodiscard]] inline std::uint8_t encode_scaled_u8(double value, double scale, double offset) {
  if (!std::isfinite(value)) {
    throw std::invalid_argument("cannot encode a non-finite CAN signal");
  }
  const double raw = std::round((value - offset) / scale);
  return static_cast<std::uint8_t>(
      std::clamp(raw, 0.0, static_cast<double>(std::numeric_limits<std::uint8_t>::max())));
}

[[nodiscard]] inline std::uint8_t encode_normalized_u8(double value) {
  return encode_scaled_u8(value, 1.0 / 255.0, 0.0);
}

inline void pack_u16_little_endian(std::array<std::uint8_t, 8>& payload, std::size_t offset,
                                   std::uint16_t value) noexcept {
  payload[offset] = static_cast<std::uint8_t>(value & 0xFFU);
  payload[offset + 1] = static_cast<std::uint8_t>((value >> 8U) & 0xFFU);
}

}  // namespace tuneros::ecu::detail
