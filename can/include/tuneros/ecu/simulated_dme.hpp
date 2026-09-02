#pragma once

#include <cstdint>

#include "tuneros/canbus/transport.hpp"
#include "tuneros/ecu/dme_frames.hpp"
#include "tuneros/simulator/contracts.hpp"

namespace tuneros::ecu {

struct DmePublicationSchedule {
  std::uint64_t fast_engine_period_microseconds{kDmeFastEnginePeriodMicroseconds};
  std::uint64_t air_load_period_microseconds{kDmeAirLoadPeriodMicroseconds};
  std::uint64_t thermal_electrical_period_microseconds{kDmeThermalElectricalPeriodMicroseconds};

  friend constexpr bool operator==(const DmePublicationSchedule&,
                                   const DmePublicationSchedule&) = default;
};

class SimulatedDme {
 public:
  explicit SimulatedDme(DmePublicationSchedule schedule = {});

  [[nodiscard]] const DmePublicationSchedule& schedule() const noexcept { return schedule_; }

  void observe_and_publish(const simulator::VehicleState& state, canbus::CanTransport& transport);
  void reset() noexcept;

 private:
  DmePublicationSchedule schedule_;
  std::uint64_t next_fast_engine_timestamp_{};
  std::uint64_t next_air_load_timestamp_{};
  std::uint64_t next_thermal_electrical_timestamp_{};
};

}  // namespace tuneros::ecu
