#include "tuneros/simulator/calibration.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <utility>

namespace tuneros::simulator {
namespace {

struct Interval {
  std::size_t lower{};
  std::size_t upper{};
  double fraction{};
};

void require_text(std::string_view value, std::string_view field) {
  if (value.empty()) {
    throw std::invalid_argument(std::string{field} + " cannot be empty");
  }
}

void require_finite(std::span<const double> values, std::string_view field) {
  if (std::any_of(values.begin(), values.end(),
                  [](double value) { return !std::isfinite(value); })) {
    throw std::invalid_argument(std::string{field} + " values must be finite");
  }
}

[[nodiscard]] Interval interval_for(std::span<const double> axis, double coordinate) noexcept {
  if (coordinate <= axis.front()) {
    return {};
  }
  if (coordinate >= axis.back()) {
    const auto last = axis.size() - 1;
    return {last, last, 0.0};
  }
  const auto upper_iterator = std::upper_bound(axis.begin(), axis.end(), coordinate);
  const auto upper = static_cast<std::size_t>(upper_iterator - axis.begin());
  const auto lower = upper - 1;
  const double fraction = (coordinate - axis[lower]) / (axis[upper] - axis[lower]);
  return {lower, upper, fraction};
}

[[nodiscard]] double interpolate(double lower, double upper, double fraction) noexcept {
  return lower + (upper - lower) * fraction;
}

[[nodiscard]] CalibrationProfile make_stock_profile() {
  return {
      .id = CalibrationId::kStock,
      .profile_id = "stock",
      .display_name = "Stock",
      .description = "TunerOS synthetic baseline calibration for the simulated N54 powertrain.",
      .revision = 1,
      .synthetic = true,
      .throttle_response = Table1D{"Throttle response",
                                   "normalized load",
                                   Axis1D{"Pedal", "normalized", {0.0, 0.25, 0.5, 0.75, 1.0}},
                                   {0.0, 0.22, 0.48, 0.74, 1.0}},
      .boost_target_kpa_gauge =
          Table2D{
              "Boost target",
              "kPa_gauge",
              Axis1D{"Engine speed", "rpm", {1'000.0, 2'500.0, 4'000.0, 5'500.0, 6'500.0}},
              Axis1D{"Load", "normalized", {0.0, 0.5, 1.0}},
              {0.0, 0.0, 0.0, 0.0, 25.0, 70.0, 0.0, 35.0, 90.0, 0.0, 28.0, 75.0, 0.0, 10.0, 40.0}},
      .lambda_target = Table1D{"Lambda target",
                               "lambda",
                               Axis1D{"Load", "normalized", {0.0, 0.5, 0.8, 1.0}},
                               {1.0, 1.0, 0.90, 0.86}},
      .ignition_target_degrees =
          Table2D{"Ignition target",
                  "degrees",
                  Axis1D{"Engine speed", "rpm", {2'000.0, 3'500.0, 5'000.0, 6'500.0}},
                  Axis1D{"Load", "normalized", {0.0, 0.5, 1.0}},
                  {18.0, 14.0, 10.0, 22.0, 15.0, 8.0, 24.0, 16.0, 7.0, 20.0, 12.0, 5.0}},
      .boost_response_time_constant_seconds = 0.80,
      .engine_output_multiplier = 1.0,
  };
}

[[nodiscard]] CalibrationProfile make_stage1_profile() {
  return {
      .id = CalibrationId::kStage1,
      .profile_id = "stage-1",
      .display_name = "Stage 1",
      .description =
          "TunerOS synthetic higher-output simulation calibration; not real tuning data.",
      .revision = 1,
      .synthetic = true,
      .throttle_response = Table1D{"Throttle response",
                                   "normalized load",
                                   Axis1D{"Pedal", "normalized", {0.0, 0.25, 0.5, 0.75, 1.0}},
                                   {0.0, 0.28, 0.60, 0.86, 1.0}},
      .boost_target_kpa_gauge =
          Table2D{"Boost target",
                  "kPa_gauge",
                  Axis1D{"Engine speed", "rpm", {1'000.0, 2'500.0, 4'000.0, 5'500.0, 6'500.0}},
                  Axis1D{"Load", "normalized", {0.0, 0.5, 1.0}},
                  {0.0, 0.0, 0.0, 0.0, 35.0, 95.0, 0.0, 50.0, 125.0, 0.0, 45.0, 110.0, 0.0, 20.0,
                   65.0}},
      .lambda_target = Table1D{"Lambda target",
                               "lambda",
                               Axis1D{"Load", "normalized", {0.0, 0.5, 0.8, 1.0}},
                               {1.0, 1.0, 0.88, 0.82}},
      .ignition_target_degrees =
          Table2D{"Ignition target",
                  "degrees",
                  Axis1D{"Engine speed", "rpm", {2'000.0, 3'500.0, 5'000.0, 6'500.0}},
                  Axis1D{"Load", "normalized", {0.0, 0.5, 1.0}},
                  {18.0, 14.0, 9.0, 22.0, 16.0, 10.0, 24.0, 18.0, 9.0, 20.0, 14.0, 7.0}},
      .boost_response_time_constant_seconds = 0.65,
      .engine_output_multiplier = 1.08,
  };
}

}  // namespace

Axis1D::Axis1D(std::string name, std::string unit, std::vector<double> breakpoints)
    : name_(std::move(name)), unit_(std::move(unit)), breakpoints_(std::move(breakpoints)) {
  require_text(name_, "axis name");
  require_text(unit_, "axis unit");
  if (breakpoints_.size() < 2) {
    throw std::invalid_argument("axis requires at least two breakpoints");
  }
  require_finite(breakpoints_, "axis");
  if (!std::is_sorted(breakpoints_.begin(), breakpoints_.end(), std::less{}) ||
      std::adjacent_find(breakpoints_.begin(), breakpoints_.end()) != breakpoints_.end()) {
    throw std::invalid_argument("axis breakpoints must be strictly increasing");
  }
}

Table1D::Table1D(std::string name, std::string value_unit, Axis1D axis, std::vector<double> values)
    : name_(std::move(name)),
      value_unit_(std::move(value_unit)),
      axis_(std::move(axis)),
      values_(std::move(values)) {
  require_text(name_, "table name");
  require_text(value_unit_, "table value unit");
  if (values_.size() != axis_.breakpoints().size()) {
    throw std::invalid_argument("1D table value count must match its axis");
  }
  require_finite(values_, "table");
}

double Table1D::lookup(double coordinate) const {
  if (!std::isfinite(coordinate)) {
    throw std::invalid_argument("1D lookup coordinate must be finite");
  }
  const auto interval = interval_for(axis_.breakpoints(), coordinate);
  return interpolate(values_[interval.lower], values_[interval.upper], interval.fraction);
}

Table2D::Table2D(std::string name, std::string value_unit, Axis1D row_axis, Axis1D column_axis,
                 std::vector<double> row_major_values)
    : name_(std::move(name)),
      value_unit_(std::move(value_unit)),
      row_axis_(std::move(row_axis)),
      column_axis_(std::move(column_axis)),
      values_(std::move(row_major_values)) {
  require_text(name_, "table name");
  require_text(value_unit_, "table value unit");
  if (values_.size() != row_axis_.breakpoints().size() * column_axis_.breakpoints().size()) {
    throw std::invalid_argument("2D table dimensions do not match its axes");
  }
  require_finite(values_, "table");
}

double Table2D::lookup(double row_coordinate, double column_coordinate) const {
  if (!std::isfinite(row_coordinate) || !std::isfinite(column_coordinate)) {
    throw std::invalid_argument("2D lookup coordinates must be finite");
  }
  const auto row = interval_for(row_axis_.breakpoints(), row_coordinate);
  const auto column = interval_for(column_axis_.breakpoints(), column_coordinate);
  const auto width = column_axis_.breakpoints().size();
  const auto at = [this, width](std::size_t row_index, std::size_t column_index) {
    return values_[row_index * width + column_index];
  };
  const double lower_row =
      interpolate(at(row.lower, column.lower), at(row.lower, column.upper), column.fraction);
  const double upper_row =
      interpolate(at(row.upper, column.lower), at(row.upper, column.upper), column.fraction);
  return interpolate(lower_row, upper_row, row.fraction);
}

std::optional<CalibrationId> calibration_id_from_name(std::string_view name) noexcept {
  if (name == "stock") {
    return CalibrationId::kStock;
  }
  if (name == "stage-1") {
    return CalibrationId::kStage1;
  }
  return std::nullopt;
}

const CalibrationProfile& calibration_profile(CalibrationId id) {
  static const CalibrationProfile stock = make_stock_profile();
  static const CalibrationProfile stage1 = make_stage1_profile();
  switch (id) {
    case CalibrationId::kStock:
      return stock;
    case CalibrationId::kStage1:
      return stage1;
  }
  throw std::invalid_argument("unknown calibration profile");
}

std::span<const CalibrationProfile* const> calibration_profiles() noexcept {
  static const std::array profiles{&calibration_profile(CalibrationId::kStock),
                                   &calibration_profile(CalibrationId::kStage1)};
  return profiles;
}

}  // namespace tuneros::simulator
