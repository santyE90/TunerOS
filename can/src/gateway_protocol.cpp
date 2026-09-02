#include "tuneros/canbus/gateway_protocol.hpp"

#include <stdexcept>

namespace tuneros::canbus {

GatewayRecord serialize_gateway_record(const CanFrame& frame) {
  if (!is_valid(frame)) {
    throw std::invalid_argument("cannot serialize an invalid Classic CAN frame");
  }

  GatewayRecord record{};
  for (std::size_t index = 0; index < sizeof(frame.timestamp_microseconds); ++index) {
    const auto shift =
        static_cast<unsigned>((sizeof(frame.timestamp_microseconds) - 1 - index) * 8);
    record[index] = static_cast<std::uint8_t>(frame.timestamp_microseconds >> shift);
  }
  record[8] = static_cast<std::uint8_t>(frame.arbitration_id >> 8);
  record[9] = static_cast<std::uint8_t>(frame.arbitration_id);
  record[10] = frame.payload_length;
  for (std::size_t index = 0; index < frame.payload_length; ++index) {
    record[11 + index] = frame.payload[index];
  }
  return record;
}

}  // namespace tuneros::canbus
