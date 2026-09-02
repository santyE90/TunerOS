#include "tuneros/ecu/dme_frames.hpp"

#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string_view>

#include "tuneros/simulator/contracts.hpp"

namespace {

using namespace tuneros;

bool expect(bool condition, std::string_view message) {
  if (!condition) {
    std::cerr << message << '\n';
  }
  return condition;
}

simulator::VehicleState representative_state() {
  return {
      .timestamp = {123'000},
      .accelerator_pedal_position = 0.50,
      .requested_scenario_load = 0.25,
      .engine_running = true,
      .engine_speed_rpm = 1500.0,
      .engine_load = 0.25,
      .throttle_position = 0.50,
      .manifold_pressure_kpa_absolute = 80.5,
      .coolant_temperature_celsius = 90.0,
      .oil_temperature_celsius = 100.0,
      .intake_air_temperature_celsius = 25.0,
      .battery_voltage_volts = 14.2,
  };
}

bool test_exact_fast_engine_layout() {
  const auto frame = ecu::make_dme_fast_engine_frame(representative_state());
  const std::array<std::uint8_t, 8> expected{0x70, 0x17, 0x80, 0x40, 0x01, 0, 0, 0};
  return expect(frame.arbitration_id == ecu::kDmeFastEngineFrameId &&
                    frame.payload_length == ecu::kDmeFastEnginePayloadLength &&
                    frame.payload == expected && frame.timestamp_microseconds == 123'000,
                "Fast-engine frame must match its exact documented little-endian layout");
}

bool test_exact_air_load_layout() {
  const auto frame = ecu::make_dme_air_load_frame(representative_state());
  const std::array<std::uint8_t, 8> expected{0x25, 0x03, 0x80, 0x40, 0, 0, 0, 0};
  return expect(frame.arbitration_id == ecu::kDmeAirLoadFrameId &&
                    frame.payload_length == ecu::kDmeAirLoadPayloadLength &&
                    frame.payload == expected && frame.timestamp_microseconds == 123'000,
                "Air/load frame must match its exact documented little-endian layout");
}

bool test_exact_thermal_electrical_layout() {
  const auto frame = ecu::make_dme_thermal_electrical_frame(representative_state());
  const std::array<std::uint8_t, 8> expected{0x6C, 0x07, 0xD0, 0x07, 0xE2, 0x04, 0x8E, 0};
  return expect(frame.arbitration_id == ecu::kDmeThermalElectricalFrameId &&
                    frame.payload_length == ecu::kDmeThermalElectricalPayloadLength &&
                    frame.payload == expected && frame.timestamp_microseconds == 123'000,
                "Thermal/electrical frame must match its exact documented layout");
}

bool test_saturation_and_non_finite_rejection() {
  auto state = representative_state();
  state.engine_speed_rpm = 100'000.0;
  state.throttle_position = -1.0;
  state.engine_load = 2.0;
  const auto saturated = ecu::make_dme_fast_engine_frame(state);
  if (!expect(saturated.payload[0] == 0xFF && saturated.payload[1] == 0xFF &&
                  saturated.payload[2] == 0x00 && saturated.payload[3] == 0xFF,
              "Out-of-range encodings must saturate rather than wrap")) {
    return false;
  }

  state = representative_state();
  state.engine_speed_rpm = std::numeric_limits<double>::infinity();
  try {
    [[maybe_unused]] const auto invalid = ecu::make_dme_fast_engine_frame(state);
    return expect(false, "Non-finite CAN signals must be rejected");
  } catch (const std::invalid_argument&) {
  }
  return true;
}

bool test_signal_endpoints_saturate() {
  auto state = representative_state();
  state.manifold_pressure_kpa_absolute = -1.0;
  state.accelerator_pedal_position = -1.0;
  state.requested_scenario_load = 2.0;
  const auto low_air = ecu::make_dme_air_load_frame(state);
  if (!expect(low_air.payload[0] == 0 && low_air.payload[1] == 0 && low_air.payload[2] == 0 &&
                  low_air.payload[3] == 0xFF,
              "Air/load values must saturate to their unsigned endpoints")) {
    return false;
  }

  state.manifold_pressure_kpa_absolute = 10'000.0;
  const auto high_air = ecu::make_dme_air_load_frame(state);
  if (!expect(high_air.payload[0] == 0xFF && high_air.payload[1] == 0xFF,
              "MAP must saturate at its uint16 maximum")) {
    return false;
  }

  state = representative_state();
  state.coolant_temperature_celsius = -200.0;
  state.oil_temperature_celsius = 10'000.0;
  state.intake_air_temperature_celsius = -100.0;
  state.battery_voltage_volts = 100.0;
  const auto thermal = ecu::make_dme_thermal_electrical_frame(state);
  return expect(thermal.payload[0] == 0 && thermal.payload[1] == 0 && thermal.payload[2] == 0xFF &&
                    thermal.payload[3] == 0xFF && thermal.payload[4] == 0 &&
                    thermal.payload[5] == 0 && thermal.payload[6] == 0xFF,
                "Temperature and voltage encodings must saturate at documented endpoints");
}

}  // namespace

int main() {
  if (!test_exact_fast_engine_layout() || !test_exact_air_load_layout() ||
      !test_exact_thermal_electrical_layout() || !test_saturation_and_non_finite_rejection() ||
      !test_signal_endpoints_saturate()) {
    return 1;
  }
  return 0;
}
