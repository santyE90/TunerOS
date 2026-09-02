#pragma once

#include <cstdint>
#include <limits>

namespace tuneros::ecu::detail {

inline void advance_due_timestamp(std::uint64_t& next_due, std::uint64_t period,
                                  std::uint64_t observed_timestamp) noexcept {
  const std::uint64_t periods_to_advance = (observed_timestamp - next_due) / period + 1;
  const std::uint64_t maximum_increment = std::numeric_limits<std::uint64_t>::max() - next_due;
  if (periods_to_advance > maximum_increment / period) {
    next_due = std::numeric_limits<std::uint64_t>::max();
    return;
  }
  next_due += periods_to_advance * period;
}

}  // namespace tuneros::ecu::detail
