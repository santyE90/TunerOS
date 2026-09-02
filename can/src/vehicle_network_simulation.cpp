#include "tuneros/ecu/vehicle_network_simulation.hpp"

#include <algorithm>
#include <utility>
#include <vector>

namespace tuneros::ecu {

VehicleNetworkPublisher::VehicleNetworkPublisher(DmePublicationSchedule dme_schedule,
                                                 DscPublicationSchedule dsc_schedule)
    : dme_(dme_schedule), dsc_(dsc_schedule) {}

void VehicleNetworkPublisher::observe_and_publish(const simulator::VehicleState& state,
                                                  canbus::CanTransport& transport) {
  auto frames = dme_.collect_due_frames(state);
  auto dsc_frames = dsc_.collect_due_frames(state);
  frames.insert(frames.end(), dsc_frames.begin(), dsc_frames.end());
  std::sort(frames.begin(), frames.end(), [](const auto& left, const auto& right) {
    return left.arbitration_id < right.arbitration_id;
  });
  for (const auto& frame : frames) {
    transport.send(frame);
  }
}

void VehicleNetworkPublisher::reset() noexcept {
  dme_.reset();
  dsc_.reset();
}

VehicleNetworkSimulation::VehicleNetworkSimulation(
    simulator::SimulationRunConfiguration configuration, DmePublicationSchedule dme_schedule,
    DscPublicationSchedule dsc_schedule)
    : vehicle_simulation_(std::move(configuration)), publisher_(dme_schedule, dsc_schedule) {
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
  publisher_.reset();
  transport_.clear();
  publish_current_state();
}

void VehicleNetworkSimulation::publish_current_state() {
  publisher_.observe_and_publish(vehicle_simulation_.state(), transport_);
}

}  // namespace tuneros::ecu
