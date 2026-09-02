#pragma once

#include <cstdint>
#include <memory>

#include "tuneros/canbus/gateway_protocol.hpp"
#include "tuneros/canbus/transport.hpp"

namespace tuneros::canbus {

class TcpCanTransport final : public CanTransport {
 public:
  ~TcpCanTransport() override;
  TcpCanTransport(TcpCanTransport&&) noexcept;
  TcpCanTransport& operator=(TcpCanTransport&&) noexcept;
  TcpCanTransport(const TcpCanTransport&) = delete;
  TcpCanTransport& operator=(const TcpCanTransport&) = delete;

  void send(const CanFrame& frame) override;

 private:
  struct Impl;
  explicit TcpCanTransport(std::unique_ptr<Impl> implementation) noexcept;

  std::unique_ptr<Impl> implementation_;
  friend class TcpCanServer;
};

// Single-client, synchronous loopback server for the Phase 2C development gateway.
class TcpCanServer {
 public:
  explicit TcpCanServer(std::uint16_t port = kDefaultGatewayPort);
  ~TcpCanServer();
  TcpCanServer(TcpCanServer&&) noexcept;
  TcpCanServer& operator=(TcpCanServer&&) noexcept;
  TcpCanServer(const TcpCanServer&) = delete;
  TcpCanServer& operator=(const TcpCanServer&) = delete;

  [[nodiscard]] std::uint16_t port() const noexcept;
  [[nodiscard]] TcpCanTransport accept_client();

 private:
  struct Impl;
  std::unique_ptr<Impl> implementation_;
};

}  // namespace tuneros::canbus
