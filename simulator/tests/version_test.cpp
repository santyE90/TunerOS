#include "tuneros/simulator/version.hpp"

#include <iostream>
#include <string_view>

int main() {
  using tuneros::simulator::component_name;
  using tuneros::simulator::version;

  if (component_name() != std::string_view{"TunerOS Simulator"}) {
    std::cerr << "Unexpected component name\n";
    return 1;
  }

  if (version().empty()) {
    std::cerr << "Version must not be empty\n";
    return 1;
  }

  return 0;
}
