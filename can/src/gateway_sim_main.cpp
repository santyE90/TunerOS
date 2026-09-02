#include <charconv>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>

#include "tuneros/canbus/gateway_protocol.hpp"
#include "tuneros/canbus/tcp_gateway.hpp"
#include "tuneros/ecu/vehicle_network_simulation.hpp"
#include "tuneros/simulator/simulation.hpp"

namespace {

struct CommandLineOptions {
  std::string scenario{"idle"};
  std::uint16_t port{tuneros::canbus::kDefaultGatewayPort};
  std::uint64_t step_microseconds{10'000};
  std::uint64_t duration_microseconds{};
};

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
      std::cout << "Usage: tuneros_gateway_sim [--scenario idle|cold-start|warmup|city] "
                   "[--port 0..65535] [--step-us positive] [--duration-us positive]\n"
                   "Port 0 requests an OS-assigned loopback port. Simulation is unpaced.\n";
      std::exit(0);
    }
    if (index + 1 >= argument_count) {
      throw std::invalid_argument(std::string{option} + " requires a value");
    }
    const std::string_view value{arguments[++index]};
    if (option == "--scenario") {
      options.scenario = value;
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
    } else {
      throw std::invalid_argument("unknown option: " + std::string{option});
    }
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
  } else {
    throw std::invalid_argument("--scenario must be one of: idle, cold-start, warmup, city");
  }

  configuration.fixed_step = SimulationDuration{options.step_microseconds};
  if (options.duration_microseconds != 0) {
    configuration.duration = SimulationDuration{options.duration_microseconds};
  }
  return configuration;
}

}  // namespace

int main(int argument_count, char** arguments) {
  try {
    const auto options = parse_options(argument_count, arguments);
    auto simulation = tuneros::simulator::VehicleSimulation{make_configuration(options)};
    tuneros::ecu::VehicleNetworkPublisher network;
    tuneros::canbus::TcpCanServer server{options.port};

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
