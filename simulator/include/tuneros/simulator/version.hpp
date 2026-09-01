#pragma once

#include <string_view>

namespace tuneros::simulator {

[[nodiscard]] constexpr std::string_view version() noexcept { return "0.1.0"; }

[[nodiscard]] std::string_view component_name() noexcept;

}  // namespace tuneros::simulator
