#include "tuneros/canbus/tcp_gateway.hpp"

#include <array>
#include <cstddef>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#endif

namespace tuneros::canbus {
namespace {

#ifdef _WIN32
using NativeSocket = SOCKET;
inline constexpr NativeSocket kInvalidSocket = INVALID_SOCKET;

int last_socket_error() noexcept { return WSAGetLastError(); }
void close_socket(NativeSocket socket) noexcept { closesocket(socket); }
void shutdown_socket(NativeSocket socket) noexcept { shutdown(socket, SD_BOTH); }
#else
using NativeSocket = int;
inline constexpr NativeSocket kInvalidSocket = -1;

int last_socket_error() noexcept { return errno; }
void close_socket(NativeSocket socket) noexcept { close(socket); }
void shutdown_socket(NativeSocket socket) noexcept { shutdown(socket, SHUT_RDWR); }
#endif

[[noreturn]] void throw_socket_error(const char* operation) {
  throw std::runtime_error(std::string{operation} + " failed with socket error " +
                           std::to_string(last_socket_error()));
}

class SocketRuntime {
 public:
  SocketRuntime() {
#ifdef _WIN32
    WSADATA data{};
    const int result = WSAStartup(MAKEWORD(2, 2), &data);
    if (result != 0) {
      throw std::runtime_error("WSAStartup failed with socket error " + std::to_string(result));
    }
#endif
  }

  ~SocketRuntime() {
#ifdef _WIN32
    WSACleanup();
#endif
  }

  SocketRuntime(const SocketRuntime&) = delete;
  SocketRuntime& operator=(const SocketRuntime&) = delete;
};

void send_all(NativeSocket socket, const std::uint8_t* bytes, std::size_t size) {
  std::size_t sent = 0;
  while (sent < size) {
#ifdef _WIN32
    const int result = ::send(socket, reinterpret_cast<const char*>(bytes + sent),
                              static_cast<int>(size - sent), 0);
    if (result == SOCKET_ERROR || result == 0) {
      throw_socket_error("send");
    }
#else
#ifdef MSG_NOSIGNAL
    const int flags = MSG_NOSIGNAL;
#else
    const int flags = 0;
#endif
    const auto result = ::send(socket, bytes + sent, size - sent, flags);
    if (result <= 0) {
      throw_socket_error("send");
    }
#endif
    sent += static_cast<std::size_t>(result);
  }
}

}  // namespace

struct TcpCanTransport::Impl {
  explicit Impl(NativeSocket accepted_socket) : socket(accepted_socket) {}

  ~Impl() {
    if (socket != kInvalidSocket) {
      shutdown_socket(socket);
      close_socket(socket);
    }
  }

  SocketRuntime runtime;
  NativeSocket socket{kInvalidSocket};
};

struct TcpCanServer::Impl {
  explicit Impl(std::uint16_t requested_port) {
    listening_socket = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (listening_socket == kInvalidSocket) {
      throw_socket_error("socket");
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = htons(requested_port);
    if (::bind(listening_socket, reinterpret_cast<const sockaddr*>(&address), sizeof(address)) !=
        0) {
      const int error = last_socket_error();
      close_socket(listening_socket);
      listening_socket = kInvalidSocket;
      throw std::runtime_error("bind to 127.0.0.1 failed with socket error " +
                               std::to_string(error));
    }
    if (::listen(listening_socket, 1) != 0) {
      const int error = last_socket_error();
      close_socket(listening_socket);
      listening_socket = kInvalidSocket;
      throw std::runtime_error("listen failed with socket error " + std::to_string(error));
    }

    sockaddr_in bound_address{};
#ifdef _WIN32
    int address_length = sizeof(bound_address);
#else
    socklen_t address_length = sizeof(bound_address);
#endif
    if (::getsockname(listening_socket, reinterpret_cast<sockaddr*>(&bound_address),
                      &address_length) != 0) {
      const int error = last_socket_error();
      close_socket(listening_socket);
      listening_socket = kInvalidSocket;
      throw std::runtime_error("getsockname failed with socket error " + std::to_string(error));
    }
    bound_port = ntohs(bound_address.sin_port);
  }

  ~Impl() {
    if (listening_socket != kInvalidSocket) {
      close_socket(listening_socket);
    }
  }

  SocketRuntime runtime;
  NativeSocket listening_socket{kInvalidSocket};
  std::uint16_t bound_port{};
};

TcpCanTransport::TcpCanTransport(std::unique_ptr<Impl> implementation) noexcept
    : implementation_(std::move(implementation)) {}
TcpCanTransport::~TcpCanTransport() = default;
TcpCanTransport::TcpCanTransport(TcpCanTransport&&) noexcept = default;
TcpCanTransport& TcpCanTransport::operator=(TcpCanTransport&&) noexcept = default;

void TcpCanTransport::send(const CanFrame& frame) {
  const auto record = serialize_gateway_record(frame);
  send_all(implementation_->socket, record.data(), record.size());
}

TcpCanServer::TcpCanServer(std::uint16_t port) : implementation_(std::make_unique<Impl>(port)) {}
TcpCanServer::~TcpCanServer() = default;
TcpCanServer::TcpCanServer(TcpCanServer&&) noexcept = default;
TcpCanServer& TcpCanServer::operator=(TcpCanServer&&) noexcept = default;

std::uint16_t TcpCanServer::port() const noexcept { return implementation_->bound_port; }

TcpCanTransport TcpCanServer::accept_client() {
  const NativeSocket accepted = ::accept(implementation_->listening_socket, nullptr, nullptr);
  if (accepted == kInvalidSocket) {
    throw_socket_error("accept");
  }

  std::unique_ptr<TcpCanTransport::Impl> implementation;
  try {
    implementation = std::make_unique<TcpCanTransport::Impl>(accepted);
  } catch (...) {
    close_socket(accepted);
    throw;
  }
  auto transport = TcpCanTransport{std::move(implementation)};
  const auto header = make_gateway_header();
  send_all(transport.implementation_->socket, header.data(), header.size());
  return transport;
}

}  // namespace tuneros::canbus
