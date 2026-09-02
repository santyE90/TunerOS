#pragma once

#include <cstdint>

#include "tuneros/canbus/in_memory_transport.hpp"
#include "tuneros/ecu/simulated_dme.hpp"
#include "tuneros/ecu/simulated_dsc.hpp"
#include "tuneros/simulator/simulation.hpp"

namespace tuneros::ecu {

class VehicleNetworkPublisher {
 public:
  explicit VehicleNetworkPublisher(DmePublicationSchedule dme_schedule = {},
                                   DscPublicationSchedule dsc_schedule = {});

  [[nodiscard]] const SimulatedDme& dme() const noexcept { return dme_; }
  [[nodiscard]] const SimulatedDsc& dsc() const noexcept { return dsc_; }

  void observe_and_publish(const simulator::VehicleState& state, canbus::CanTransport& transport);
  void reset() noexcept;

 private:
  SimulatedDme dme_;
  SimulatedDsc dsc_;
};

class VehicleNetworkSimulation {
 public:
  explicit VehicleNetworkSimulation(simulator::SimulationRunConfiguration configuration,
                                    DmePublicationSchedule dme_schedule = {},
                                    DscPublicationSchedule dsc_schedule = {});

  [[nodiscard]] const simulator::VehicleSimulation& vehicle_simulation() const noexcept {
    return vehicle_simulation_;
  }
  [[nodiscard]] const SimulatedDme& dme() const noexcept { return publisher_.dme(); }
  [[nodiscard]] const SimulatedDsc& dsc() const noexcept { return publisher_.dsc(); }
  [[nodiscard]] const canbus::InMemoryTransport& transport() const noexcept { return transport_; }
  [[nodiscard]] canbus::InMemoryTransport& transport() noexcept { return transport_; }

  bool tick();
  std::uint64_t run_to_completion();
  void reset();

 private:
  void publish_current_state();

  simulator::VehicleSimulation vehicle_simulation_;
  VehicleNetworkPublisher publisher_;
  canbus::InMemoryTransport transport_;
};

}  // namespace tuneros::ecu
