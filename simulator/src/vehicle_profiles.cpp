#include "tuneros/simulator/vehicle_profiles.hpp"

namespace tuneros::simulator {

VehicleProfile make_e90_335i_n54_manual_profile() {
  return {
      .profile_id = "bmw-e90-335i-n54-2010-manual",
      .manufacturer = "BMW",
      .model = "335i",
      .chassis = "E90",
      .model_year = 2010,
      .engine_family = "N54",
      .engine_identifier = "N54B30",
      .cylinder_count = 6,
      .displacement_liters = 2.979,
      .fuel_type = "gasoline",
      .induction_type = InductionType::kTwinTurbo,
      .transmission_type = TransmissionType::kManual,
      .forward_gear_count = 6,
      .redline_rpm = 7000.0,
      .baseline_calibration_id = "tuneros-n54-stock-baseline-v0",
  };
}

}  // namespace tuneros::simulator
