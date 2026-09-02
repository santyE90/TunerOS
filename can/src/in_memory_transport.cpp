#include "tuneros/canbus/in_memory_transport.hpp"

#include <stdexcept>

namespace tuneros::canbus {

void InMemoryTransport::send(const CanFrame& frame) {
  if (!is_valid(frame)) {
    throw std::invalid_argument("invalid Classic CAN data frame");
  }
  frames_.push_back(frame);
}

std::optional<CanFrame> InMemoryTransport::receive() {
  if (frames_.empty()) {
    return std::nullopt;
  }
  CanFrame frame = frames_.front();
  frames_.pop_front();
  return frame;
}

std::vector<CanFrame> InMemoryTransport::drain() {
  std::vector<CanFrame> drained;
  drained.reserve(frames_.size());
  while (!frames_.empty()) {
    drained.push_back(frames_.front());
    frames_.pop_front();
  }
  return drained;
}

void InMemoryTransport::clear() noexcept { frames_.clear(); }

}  // namespace tuneros::canbus
