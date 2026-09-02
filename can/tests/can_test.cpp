#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <vector>

#include "tuneros/canbus/frame.hpp"
#include "tuneros/canbus/in_memory_transport.hpp"

namespace {

using namespace tuneros::canbus;

bool expect(bool condition, std::string_view message) {
  if (!condition) {
    std::cerr << message << '\n';
  }
  return condition;
}

CanFrame make_frame(std::uint16_t id, std::uint8_t length, std::uint8_t first_byte,
                    std::uint64_t timestamp) {
  CanFrame frame{
      .arbitration_id = id,
      .payload_length = length,
      .timestamp_microseconds = timestamp,
  };
  frame.payload[0] = first_byte;
  return frame;
}

bool test_frame_contract() {
  for (std::uint8_t length = 0; length <= kMaximumClassicCanPayloadLength; ++length) {
    if (!expect(is_valid(make_frame(kMaximumStandardArbitrationId, length, 0, 0)),
                "Every Classic CAN DLC from zero through eight must be valid")) {
      return false;
    }
  }

  const auto invalid_id = make_frame(0x800, 8, 0, 0);
  const auto invalid_length = make_frame(0x100, 9, 0, 0);
  const auto first = make_frame(0x123, 2, 0xAB, 42);
  const auto duplicate = first;
  return expect(!is_valid(invalid_id), "A standard identifier above 0x7FF must be invalid") &&
         expect(!is_valid(invalid_length), "A Classic CAN DLC above eight must be invalid") &&
         expect(
             first == duplicate && first.payload[0] == 0xAB && first.timestamp_microseconds == 42,
             "Frame equality must preserve identifier, DLC, bytes, and simulation timestamp");
}

bool test_fifo_transport() {
  InMemoryTransport transport;
  if (!expect(transport.empty() && transport.size() == 0 && !transport.receive().has_value(),
              "A new transport must be an empty FIFO")) {
    return false;
  }

  const auto first = make_frame(0x101, 1, 0x11, 10);
  const auto second = make_frame(0x102, 1, 0x22, 20);
  transport.send(first);
  transport.send(second);
  if (!expect(transport.size() == 2 && transport.queued_frames()[0] == first &&
                  transport.queued_frames()[1] == second,
              "Transport must preserve exact insertion order and payloads")) {
    return false;
  }

  const auto received = transport.receive();
  if (!expect(received == first && transport.size() == 1,
              "Receive must pop exactly the oldest frame")) {
    return false;
  }
  const auto drained = transport.drain();
  if (!expect(drained == std::vector<CanFrame>{second} && transport.empty(),
              "Drain must return the remaining FIFO sequence and empty the transport")) {
    return false;
  }

  transport.send(first);
  transport.clear();
  if (!expect(transport.empty(), "Clear must reset the in-memory queue")) {
    return false;
  }

  try {
    transport.send(make_frame(0x800, 1, 0, 0));
    return expect(false, "Transport must reject invalid frames");
  } catch (const std::invalid_argument&) {
  }
  return true;
}

}  // namespace

int main() {
  if (!test_frame_contract() || !test_fifo_transport()) {
    return 1;
  }
  return 0;
}
