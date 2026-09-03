#pragma once

#include <array>
#include <cstdint>
#include <vector>

#include "tuneros/canbus/transport.hpp"
#include "tuneros/ecu/dsc_frames.hpp"
#include "tuneros/simulator/contracts.hpp"

namespace tuneros::ecu {

struct DscPublicationSchedule {
  std::uint64_t vehicle_motion_period_microseconds{kDscVehicleMotionPeriodMicroseconds};
  std::uint64_t wheel_speeds_period_microseconds{kDscWheelSpeedsPeriodMicroseconds};

  friend constexpr bool operator==(const DscPublicationSchedule&,
                                   const DscPublicationSchedule&) = default;
};

class SimulatedDsc {
 public:
  explicit SimulatedDsc(DscPublicationSchedule schedule = {});

  [[nodiscard]] const DscPublicationSchedule& schedule() const noexcept { return schedule_; }
  [[nodiscard]] std::vector<canbus::CanFrame> collect_due_frames(
      const simulator::VehicleState& state);
  [[nodiscard]] std::vector<canbus::CanFrame> collect_due_frames(
      const simulator::VehicleState& state,
      const std::array<double, 4>& wheel_speeds_meters_per_second);
  void observe_and_publish(const simulator::VehicleState& state, canbus::CanTransport& transport);
  void reset() noexcept;

 private:
  DscPublicationSchedule schedule_;
  std::uint64_t next_vehicle_motion_timestamp_{};
  std::uint64_t next_wheel_speeds_timestamp_{};
};

}  // namespace tuneros::ecu
