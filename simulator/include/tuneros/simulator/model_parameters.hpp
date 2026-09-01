#pragma once

#include <cstdint>

namespace tuneros::simulator::model_parameters {

// TunerOS modeling assumptions. These are not BMW calibration values.
inline constexpr double kIdleTargetRpm = 750.0;
inline constexpr double kInitialEngineSpeedRpm = 850.0;
inline constexpr double kIdleRpmTimeConstantSeconds = 1.5;

inline constexpr double kInitialCoolantAboveAmbientCelsius = 5.0;
inline constexpr double kCoolantIdleEquilibriumCelsius = 92.0;
inline constexpr double kCoolantWarmupTimeConstantSeconds = 300.0;

inline constexpr double kInitialOilAboveAmbientCelsius = 2.0;
inline constexpr double kOilIdleEquilibriumCelsius = 100.0;
inline constexpr double kOilWarmupTimeConstantSeconds = 600.0;

inline constexpr double kInitialIntakeAirAboveAmbientCelsius = 3.0;
inline constexpr double kIntakeAirAboveAmbientAtIdleCelsius = 10.0;
inline constexpr double kIntakeAirTimeConstantSeconds = 60.0;

inline constexpr double kInitialBatteryVoltageVolts = 13.8;
inline constexpr double kChargingVoltageVolts = 14.2;
inline constexpr double kBatteryVoltageTimeConstantSeconds = 1.0;

inline constexpr double kIdleEngineLoad = 0.18;
inline constexpr double kIdleThrottlePosition = 0.06;
inline constexpr double kIdleRequestedScenarioLoad = 0.10;
inline constexpr double kIdleManifoldPressureFractionOfAmbient = 0.40;
inline constexpr double kIdleLambda = 1.0;
inline constexpr double kIdleIgnitionAdvanceDegrees = 8.0;

inline constexpr double kRestingBatteryVoltageVolts = 12.6;
inline constexpr double kColdStartCoolantAboveAmbientCelsius = 0.0;
inline constexpr double kColdStartOilAboveAmbientCelsius = 0.0;
inline constexpr double kColdStartElevatedRequestedScenarioLoad = 0.40;
inline constexpr double kColdStartElevatedRpmTarget = 1200.0;
inline constexpr double kColdStartRpmResponseTimeConstantSeconds = 0.75;
inline constexpr double kColdStartEngineLoadIncrease = 0.30;
inline constexpr double kColdStartThrottleIncrease = 0.04;

inline constexpr double kWarmupCoolantAboveAmbientCelsius = 20.0;
inline constexpr double kWarmupOilAboveAmbientCelsius = 15.0;
inline constexpr double kWarmupIntakeAirAboveAmbientCelsius = 5.0;

inline constexpr std::uint64_t kColdStartRequestTimestampMicroseconds = 1'000'000;
inline constexpr std::uint64_t kColdStartStabilizationDurationMicroseconds = 20'000'000;
inline constexpr std::uint64_t kDefaultIdleDurationMicroseconds = 60'000'000;
inline constexpr std::uint64_t kDefaultColdStartDurationMicroseconds = 90'000'000;
inline constexpr std::uint64_t kDefaultWarmupDurationMicroseconds = 300'000'000;

}  // namespace tuneros::simulator::model_parameters
