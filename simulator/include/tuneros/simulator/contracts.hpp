#pragma once

#include <cstdint>
#include <string>

namespace tuneros::simulator {

// Simulation time is monotonic time since the start of a run, never wall-clock time.
struct SimulationTimestamp {
  std::uint64_t microseconds{};

  friend constexpr bool operator==(const SimulationTimestamp&,
                                   const SimulationTimestamp&) = default;
};

struct SimulationDuration {
  std::uint64_t microseconds{};

  friend constexpr bool operator==(const SimulationDuration&, const SimulationDuration&) = default;
};

inline constexpr SimulationDuration kBaseSimulationStep{10'000};

enum class SimulationRunState : std::uint8_t { kStopped, kRunning, kPaused, kCompleted };

enum class ScenarioId : std::uint8_t {
  kIdle,
  kColdStart,
  kWarmup,
  kCity,
  kHighway,
  kSpirited,
  kWideOpenThrottlePull,
  kDynoPull,
};

enum class InductionType : std::uint8_t { kNaturallyAspirated, kTwinTurbo };

enum class TransmissionType : std::uint8_t { kManual, kAutomatic };

struct VehicleProfile {
  std::string profile_id;
  std::string manufacturer;
  std::string model;
  std::string chassis;
  std::uint16_t model_year{};
  std::string engine_family;
  std::string engine_identifier;
  std::uint8_t cylinder_count{};
  double displacement_liters{};
  std::string fuel_type;
  InductionType induction_type{InductionType::kNaturallyAspirated};
  TransmissionType transmission_type{TransmissionType::kManual};
  std::uint8_t forward_gear_count{};
  double redline_rpm{};
  std::string baseline_calibration_id;

  friend bool operator==(const VehicleProfile&, const VehicleProfile&) = default;
};

struct EnvironmentState {
  double ambient_temperature_celsius{20.0};
  double ambient_pressure_kpa_absolute{101.325};

  friend constexpr bool operator==(const EnvironmentState&, const EnvironmentState&) = default;
};

// Canonical pre-ECU vehicle state. Field names carry their unit where practical.
struct VehicleState {
  SimulationTimestamp timestamp{};
  SimulationRunState run_state{SimulationRunState::kStopped};

  double accelerator_pedal_position{};  // normalized [0, 1]
  double requested_scenario_load{};     // normalized [0, 1]

  bool engine_running{};
  double engine_speed_rpm{};
  double engine_load{};        // normalized [0, 1]
  double throttle_position{};  // normalized [0, 1]

  double vehicle_speed_meters_per_second{};
  std::int8_t current_gear{};  // 0 neutral; positive values are forward gears; no reverse model

  double ambient_pressure_kpa_absolute{};
  double manifold_pressure_kpa_absolute{};
  double requested_boost_kpa_gauge{};

  double coolant_temperature_celsius{};
  double oil_temperature_celsius{};
  double intake_air_temperature_celsius{};

  double lambda{};
  double ignition_advance_degrees{};
  double timing_correction_degrees{};  // zero or negative: aggregate commanded retard

  double battery_voltage_volts{};

  [[nodiscard]] double actual_boost_kpa_gauge() const noexcept {
    return manifold_pressure_kpa_absolute - ambient_pressure_kpa_absolute;
  }

  friend constexpr bool operator==(const VehicleState&, const VehicleState&) = default;
};

// Aggregate contracts remain easy to construct. These non-throwing helpers validate data at
// loading and test boundaries; they do not evolve simulation state.
[[nodiscard]] bool is_valid(const VehicleProfile& profile) noexcept;
[[nodiscard]] bool is_valid(const EnvironmentState& environment) noexcept;
[[nodiscard]] bool is_valid(const VehicleState& state, const VehicleProfile& profile) noexcept;

}  // namespace tuneros::simulator
