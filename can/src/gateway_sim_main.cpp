#include <charconv>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>

#include "tuneros/canbus/gateway_protocol.hpp"
#include "tuneros/canbus/tcp_gateway.hpp"
#include "tuneros/ecu/vehicle_network_simulation.hpp"
#include "tuneros/simulator/calibration.hpp"
#include "tuneros/simulator/faults.hpp"
#include "tuneros/simulator/simulation.hpp"

namespace {

struct CommandLineOptions {
  std::string scenario{"idle"};
  std::uint16_t port{tuneros::canbus::kDefaultGatewayPort};
  std::uint64_t step_microseconds{10'000};
  std::uint64_t duration_microseconds{};
  tuneros::simulator::CalibrationId calibration{tuneros::simulator::CalibrationId::kStock};
  bool calibration_option_seen{};
  std::optional<tuneros::simulator::FaultId> fault{};
  std::uint64_t fault_activation_microseconds{};
  std::optional<std::uint64_t> fault_deactivation_microseconds{};
  bool fault_timing_option_seen{};
};

tuneros::simulator::FaultId parse_fault(std::string_view name) {
  using tuneros::simulator::FaultId;
  if (name == "cooling-degradation") {
    return FaultId::kCoolingSystemDegradation;
  }
  if (name == "charging-failure") {
    return FaultId::kChargingSystemFailure;
  }
  if (name == "map-sensor-bias") {
    return FaultId::kMapSensorBias;
  }
  if (name == "front-left-wheel-speed-sensor-bias") {
    return FaultId::kFrontLeftWheelSpeedSensorBias;
  }
  throw std::invalid_argument(
      "--fault must be one of: cooling-degradation, charging-failure, map-sensor-bias, "
      "front-left-wheel-speed-sensor-bias");
}

std::uint64_t parse_unsigned(std::string_view text, std::string_view option) {
  std::uint64_t value{};
  const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
  if (error != std::errc{} || end != text.data() + text.size()) {
    throw std::invalid_argument(std::string{option} + " requires an unsigned integer");
  }
  return value;
}

CommandLineOptions parse_options(int argument_count, char** arguments) {
  CommandLineOptions options;
  for (int index = 1; index < argument_count; ++index) {
    const std::string_view option{arguments[index]};
    if (option == "--help") {
      std::cout << "Usage: tuneros_gateway_sim [--scenario idle|cold-start|warmup|city|wot-pull] "
                   "[--port 0..65535] [--step-us positive] [--duration-us positive] "
                   "[--calibration stock|stage-1] "
                   "[--fault cooling-degradation|charging-failure|map-sensor-bias|"
                   "front-left-wheel-speed-sensor-bias] [--fault-at-us nonnegative] "
                   "[--fault-clear-at-us greater-than-activation]\n"
                   "Port 0 requests an OS-assigned loopback port. Simulation is unpaced.\n";
      std::exit(0);
    }
    if (index + 1 >= argument_count) {
      throw std::invalid_argument(std::string{option} + " requires a value");
    }
    const std::string_view value{arguments[++index]};
    if (option == "--scenario") {
      options.scenario = value;
    } else if (option == "--calibration") {
      const auto calibration = tuneros::simulator::calibration_id_from_name(value);
      if (!calibration.has_value()) {
        throw std::invalid_argument("--calibration must be one of: stock, stage-1");
      }
      options.calibration = *calibration;
      options.calibration_option_seen = true;
    } else if (option == "--port") {
      const auto parsed = parse_unsigned(value, option);
      if (parsed > 65'535) {
        throw std::invalid_argument("--port must be in [0, 65535]");
      }
      options.port = static_cast<std::uint16_t>(parsed);
    } else if (option == "--step-us") {
      options.step_microseconds = parse_unsigned(value, option);
      if (options.step_microseconds == 0) {
        throw std::invalid_argument("--step-us must be positive");
      }
    } else if (option == "--duration-us") {
      options.duration_microseconds = parse_unsigned(value, option);
      if (options.duration_microseconds == 0) {
        throw std::invalid_argument("--duration-us must be positive");
      }
    } else if (option == "--fault") {
      if (options.fault.has_value()) {
        throw std::invalid_argument("only one --fault is supported by the Phase 7B CLI");
      }
      options.fault = parse_fault(value);
    } else if (option == "--fault-at-us") {
      options.fault_activation_microseconds = parse_unsigned(value, option);
      options.fault_timing_option_seen = true;
    } else if (option == "--fault-clear-at-us") {
      options.fault_deactivation_microseconds = parse_unsigned(value, option);
      options.fault_timing_option_seen = true;
    } else {
      throw std::invalid_argument("unknown option: " + std::string{option});
    }
  }
  if (!options.fault.has_value() && options.fault_timing_option_seen) {
    throw std::invalid_argument("fault timing options require --fault");
  }
  if (options.fault_deactivation_microseconds.has_value() &&
      *options.fault_deactivation_microseconds <= options.fault_activation_microseconds) {
    throw std::invalid_argument("--fault-clear-at-us must be greater than --fault-at-us");
  }
  return options;
}

tuneros::simulator::SimulationRunConfiguration make_configuration(
    const CommandLineOptions& options) {
  using namespace tuneros::simulator;
  SimulationRunConfiguration configuration;
  if (options.scenario == "idle") {
    configuration = make_default_idle_run_configuration();
  } else if (options.scenario == "cold-start") {
    configuration = make_default_cold_start_run_configuration();
  } else if (options.scenario == "warmup") {
    configuration = make_default_warmup_run_configuration();
  } else if (options.scenario == "city") {
    configuration = make_default_city_run_configuration();
  } else if (options.scenario == "wot-pull") {
    configuration = make_default_wot_pull_run_configuration();
  } else {
    throw std::invalid_argument(
        "--scenario must be one of: idle, cold-start, warmup, city, wot-pull");
  }

  configuration.calibration = options.calibration;
  configuration.fixed_step = SimulationDuration{options.step_microseconds};
  if (options.duration_microseconds != 0) {
    configuration.duration = SimulationDuration{options.duration_microseconds};
  }
  if (options.fault.has_value()) {
    configuration.faults.push_back({
        .id = *options.fault,
        .activation_time = SimulationTimestamp{options.fault_activation_microseconds},
        .deactivation_time =
            options.fault_deactivation_microseconds.has_value()
                ? std::optional{SimulationTimestamp{*options.fault_deactivation_microseconds}}
                : std::nullopt,
    });
  }
  return configuration;
}

}  // namespace

int main(int argument_count, char** arguments) {
  try {
    const auto options = parse_options(argument_count, arguments);
    const auto configuration = make_configuration(options);
    auto simulation = tuneros::simulator::VehicleSimulation{configuration};
    tuneros::ecu::DmePublicationSchedule dme_schedule;
    dme_schedule.combustion_observation_enabled =
        configuration.scenario == tuneros::simulator::ScenarioId::kWideOpenThrottlePull;
    tuneros::ecu::VehicleNetworkPublisher network{dme_schedule, {}, configuration.faults};
    tuneros::canbus::TcpCanServer server{options.port};

    if (options.fault.has_value()) {
      std::cerr << "FAULT " << tuneros::simulator::fault_name(*options.fault) << " active-at-us "
                << options.fault_activation_microseconds;
      if (options.fault_deactivation_microseconds.has_value()) {
        std::cerr << " clear-at-us " << *options.fault_deactivation_microseconds;
      }
      std::cerr << '\n';
    }
    if (options.calibration_option_seen ||
        configuration.scenario == tuneros::simulator::ScenarioId::kWideOpenThrottlePull) {
      std::cerr << "CALIBRATION "
                << tuneros::simulator::calibration_id_name(configuration.calibration)
                << " revision "
                << tuneros::simulator::calibration_profile(configuration.calibration).revision
                << " (TunerOS synthetic simulation only)\n";
    }

    std::cout << "LISTENING " << server.port() << '\n' << std::flush;
    auto transport = server.accept_client();

    network.observe_and_publish(simulation.state(), transport);
    while (simulation.tick()) {
      network.observe_and_publish(simulation.state(), transport);
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "ERROR: " << error.what() << '\n';
    return 1;
  }
}
