#pragma once

#include "tuneros/canbus/frame.hpp"

namespace tuneros::canbus {

class CanTransport {
 public:
  virtual ~CanTransport() = default;
  virtual void send(const CanFrame& frame) = 0;
};

}  // namespace tuneros::canbus
