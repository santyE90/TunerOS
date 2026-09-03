#pragma once

#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace tuneros::simulator {

enum class CalibrationId : std::uint8_t { kStock, kStage1 };

class Axis1D {
 public:
  Axis1D(std::string name, std::string unit, std::vector<double> breakpoints);

  [[nodiscard]] const std::string& name() const noexcept { return name_; }
  [[nodiscard]] const std::string& unit() const noexcept { return unit_; }
  [[nodiscard]] std::span<const double> breakpoints() const noexcept { return breakpoints_; }

 private:
  std::string name_;
  std::string unit_;
  std::vector<double> breakpoints_;
};

class Table1D {
 public:
  Table1D(std::string name, std::string value_unit, Axis1D axis, std::vector<double> values);

  [[nodiscard]] double lookup(double coordinate) const;
  [[nodiscard]] const std::string& name() const noexcept { return name_; }
  [[nodiscard]] const std::string& value_unit() const noexcept { return value_unit_; }
  [[nodiscard]] const Axis1D& axis() const noexcept { return axis_; }
  [[nodiscard]] std::span<const double> values() const noexcept { return values_; }

 private:
  std::string name_;
  std::string value_unit_;
  Axis1D axis_;
  std::vector<double> values_;
};

class Table2D {
 public:
  Table2D(std::string name, std::string value_unit, Axis1D row_axis, Axis1D column_axis,
          std::vector<double> row_major_values);

  [[nodiscard]] double lookup(double row_coordinate, double column_coordinate) const;
  [[nodiscard]] const std::string& name() const noexcept { return name_; }
  [[nodiscard]] const std::string& value_unit() const noexcept { return value_unit_; }
  [[nodiscard]] const Axis1D& row_axis() const noexcept { return row_axis_; }
  [[nodiscard]] const Axis1D& column_axis() const noexcept { return column_axis_; }
  [[nodiscard]] std::span<const double> values() const noexcept { return values_; }

 private:
  std::string name_;
  std::string value_unit_;
  Axis1D row_axis_;
  Axis1D column_axis_;
  std::vector<double> values_;
};

struct CalibrationProfile {
  CalibrationId id;
  std::string profile_id;
  std::string display_name;
  std::string description;
  std::uint32_t revision{};
  bool synthetic{};
  Table1D throttle_response;
  Table2D boost_target_kpa_gauge;
  Table1D lambda_target;
  Table2D ignition_target_degrees;
  double boost_response_time_constant_seconds{};
  double engine_output_multiplier{};
};

[[nodiscard]] constexpr std::string_view calibration_id_name(CalibrationId id) noexcept {
  switch (id) {
    case CalibrationId::kStock:
      return "stock";
    case CalibrationId::kStage1:
      return "stage-1";
  }
  return "unknown";
}

[[nodiscard]] std::optional<CalibrationId> calibration_id_from_name(std::string_view name) noexcept;
[[nodiscard]] const CalibrationProfile& calibration_profile(CalibrationId id);
[[nodiscard]] std::span<const CalibrationProfile* const> calibration_profiles() noexcept;

}  // namespace tuneros::simulator
