#include "tuneros/ecu/vehicle_network_simulation.hpp"

#include <utility>

namespace tuneros::ecu {

VehicleNetworkSimulation::VehicleNetworkSimulation(
    simulator::SimulationRunConfiguration configuration,
    DmePublicationSchedule publication_schedule)
    : vehicle_simulation_(std::move(configuration)), dme_(publication_schedule) {
  publish_current_state();
}

bool VehicleNetworkSimulation::tick() {
  if (!vehicle_simulation_.tick()) {
    return false;
  }
  publish_current_state();
  return true;
}

std::uint64_t VehicleNetworkSimulation::run_to_completion() {
  std::uint64_t ticks{};
  while (tick()) {
    ++ticks;
  }
  return ticks;
}

void VehicleNetworkSimulation::reset() {
  vehicle_simulation_.reset();
  dme_.reset();
  transport_.clear();
  publish_current_state();
}

void VehicleNetworkSimulation::publish_current_state() {
  dme_.observe_and_publish(vehicle_simulation_.state(), transport_);
}

}  // namespace tuneros::ecu
