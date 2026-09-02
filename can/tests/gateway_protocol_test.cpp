#include "tuneros/canbus/gateway_protocol.hpp"

#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string_view>

namespace {

using namespace tuneros::canbus;

bool expect(bool condition, std::string_view message) {
  if (!condition) {
    std::cerr << message << '\n';
  }
  return condition;
}

bool test_header() {
  constexpr GatewayHeader expected{0x54, 0x4E, 0x43, 0x52, 0x01, 0x00, 0x00, 0x00};
  return expect(make_gateway_header() == expected,
                "Gateway connection header must match the version-one golden bytes");
}

bool test_record() {
  CanFrame frame{
      .arbitration_id = 0x500,
      .payload_length = 5,
      .payload = {0x70, 0x17, 0x80, 0x40, 0x01, 0xAA, 0xBB, 0xCC},
      .timestamp_microseconds = 12'345'678,
  };
  constexpr GatewayRecord expected{0x00, 0x00, 0x00, 0x00, 0x00, 0xBC, 0x61, 0x4E, 0x05, 0x00,
                                   0x05, 0x70, 0x17, 0x80, 0x40, 0x01, 0x00, 0x00, 0x00};
  return expect(serialize_gateway_record(frame) == expected,
                "Record must encode metadata big-endian, preserve DLC bytes, and zero padding");
}

bool test_invalid_frame() {
  try {
    [[maybe_unused]] const auto record =
        serialize_gateway_record(CanFrame{.arbitration_id = 0x800, .payload_length = 1});
    return expect(false, "Invalid CAN frames must be rejected by the gateway serializer");
  } catch (const std::invalid_argument&) {
  }
  try {
    [[maybe_unused]] const auto record =
        serialize_gateway_record(CanFrame{.arbitration_id = 0x100, .payload_length = 9});
    return expect(false, "Invalid Classic CAN DLC must be rejected by the gateway serializer");
  } catch (const std::invalid_argument&) {
    return true;
  }
}

}  // namespace

int main() { return test_header() && test_record() && test_invalid_frame() ? 0 : 1; }
