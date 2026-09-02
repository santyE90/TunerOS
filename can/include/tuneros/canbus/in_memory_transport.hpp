#pragma once

#include <cstddef>
#include <deque>
#include <optional>
#include <vector>

#include "tuneros/canbus/transport.hpp"

namespace tuneros::canbus {

class InMemoryTransport final : public CanTransport {
 public:
  void send(const CanFrame& frame) override;

  [[nodiscard]] bool empty() const noexcept { return frames_.empty(); }
  [[nodiscard]] std::size_t size() const noexcept { return frames_.size(); }
  [[nodiscard]] const std::deque<CanFrame>& queued_frames() const noexcept { return frames_; }

  [[nodiscard]] std::optional<CanFrame> receive();
  [[nodiscard]] std::vector<CanFrame> drain();
  void clear() noexcept;

 private:
  std::deque<CanFrame> frames_;
};

}  // namespace tuneros::canbus
