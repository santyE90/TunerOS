#pragma once

#include <cstdint>

#include "tuneros/simulator/contracts.hpp"
#include "tuneros/simulator/faults.hpp"
#include "tuneros/simulator/initial_conditions.hpp"
#include "tuneros/simulator/simulation_clock.hpp"

namespace tuneros::simulator {

struct SimulationRunConfiguration {
  VehicleProfile vehicle_profile;
  ScenarioId scenario{ScenarioId::kIdle};
  SimulationDuration duration{60'000'000};
  SimulationDuration fixed_step{kBaseSimulationStep};
  EnvironmentState environment{};
  SimulationInitialConditions initial_conditions{};
  FaultConfigurations faults{};

  friend bool operator==(const SimulationRunConfiguration&,
                         const SimulationRunConfiguration&) = default;
};

[[nodiscard]] SimulationRunConfiguration make_default_idle_run_configuration(
    EnvironmentState environment = {});
[[nodiscard]] SimulationRunConfiguration make_default_cold_start_run_configuration(
    EnvironmentState environment = {});
[[nodiscard]] SimulationRunConfiguration make_default_warmup_run_configuration(
    EnvironmentState environment = {});
[[nodiscard]] SimulationRunConfiguration make_default_city_run_configuration(
    EnvironmentState environment = {});

class VehicleSimulation {
 public:
  explicit VehicleSimulation(SimulationRunConfiguration configuration);

  [[nodiscard]] const SimulationRunConfiguration& configuration() const noexcept {
    return configuration_;
  }
  [[nodiscard]] const SimulationClock& clock() const noexcept { return clock_; }
  [[nodiscard]] const VehicleState& state() const noexcept { return state_; }

  // Returns true only when one simulation step was executed.
  bool tick();
  std::uint64_t advance_ticks(std::uint64_t count);
  std::uint64_t run_to_completion();

  void pause() noexcept;
  void resume() noexcept;
  void reset() noexcept;

 private:
  SimulationRunConfiguration configuration_;
  SimulationClock clock_;
  VehicleState initial_state_;
  VehicleState state_;
};

}  // namespace tuneros::simulator
