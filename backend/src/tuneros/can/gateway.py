"""Synchronous TCP reader for the versioned TunerOS raw-CAN gateway."""

import socket
import struct
from collections.abc import Iterator
from types import TracebackType

from tuneros.can.models import RawCanFrame

GATEWAY_MAGIC = b"TNCR"
GATEWAY_PROTOCOL_VERSION = 1
GATEWAY_HEADER_SIZE = 8
GATEWAY_RECORD_SIZE = 19
DEFAULT_GATEWAY_HOST = "127.0.0.1"
DEFAULT_GATEWAY_PORT = 45_800

_HEADER = struct.Struct("!4sB3s")
_RECORD = struct.Struct("!QHB8s")


class GatewayError(Exception):
    """Base error for the local raw-CAN gateway."""


class GatewayProtocolError(GatewayError):
    """Raised for an unsupported or malformed gateway byte stream."""


class GatewayConnectionError(GatewayError):
    """Raised when the gateway connection cannot be opened or read."""


def decode_gateway_header(data: bytes) -> None:
    """Validate one complete connection header."""

    if len(data) != GATEWAY_HEADER_SIZE:
        raise GatewayProtocolError(
            f"gateway header requires {GATEWAY_HEADER_SIZE} bytes, got {len(data)}"
        )
    magic, version, reserved = _HEADER.unpack(data)
    if magic != GATEWAY_MAGIC:
        raise GatewayProtocolError(f"invalid gateway magic {magic!r}")
    if version != GATEWAY_PROTOCOL_VERSION:
        raise GatewayProtocolError(f"unsupported gateway protocol version {version}")
    if reserved != b"\x00\x00\x00":
        raise GatewayProtocolError("gateway header reserved bytes must be zero")


def decode_gateway_record(data: bytes) -> RawCanFrame:
    """Decode one complete fixed-size wire record into the existing raw-frame contract."""

    if len(data) != GATEWAY_RECORD_SIZE:
        raise GatewayProtocolError(
            f"gateway record requires {GATEWAY_RECORD_SIZE} bytes, got {len(data)}"
        )
    timestamp, arbitration_id, dlc, padded_payload = _RECORD.unpack(data)
    if arbitration_id > 0x7FF:
        raise GatewayProtocolError(
            f"received invalid standard CAN arbitration ID 0x{arbitration_id:X}"
        )
    if dlc > 8:
        raise GatewayProtocolError(f"received invalid Classic CAN DLC {dlc}")
    return RawCanFrame(arbitration_id, padded_payload[:dlc], timestamp)


class RawCanGatewayClient:
    """One synchronous client yielding raw frames in authoritative stream order."""

    def __init__(self, connection: socket.socket) -> None:
        self._connection = connection
        self._closed = False
        try:
            decode_gateway_header(self._read_exact(GATEWAY_HEADER_SIZE, "connection header"))
        except Exception:
            self.close()
            raise

    @classmethod
    def connect(
        cls,
        host: str = DEFAULT_GATEWAY_HOST,
        port: int = DEFAULT_GATEWAY_PORT,
        *,
        timeout: float | None = None,
    ) -> "RawCanGatewayClient":
        """Connect and validate the server's protocol header."""

        try:
            connection = socket.create_connection((host, port), timeout=timeout)
        except OSError as error:
            raise GatewayConnectionError(
                f"could not connect to gateway at {host}:{port}"
            ) from error
        try:
            return cls(connection)
        except Exception:
            connection.close()
            raise

    def _read_exact(self, size: int, description: str, *, allow_clean_eof: bool = False) -> bytes:
        data = bytearray()
        while len(data) < size:
            try:
                chunk = self._connection.recv(size - len(data))
            except OSError as error:
                raise GatewayConnectionError(f"failed reading gateway {description}") from error
            if not chunk:
                if allow_clean_eof and not data:
                    return b""
                raise GatewayProtocolError(
                    f"truncated gateway {description}: received {len(data)} of {size} bytes"
                )
            data.extend(chunk)
        return bytes(data)

    def frames(self) -> Iterator[RawCanFrame]:
        """Yield complete frames until normal record-boundary EOF."""

        while True:
            record = self._read_exact(GATEWAY_RECORD_SIZE, "record", allow_clean_eof=True)
            if not record:
                return
            yield decode_gateway_record(record)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._connection.close()

    def __enter__(self) -> "RawCanGatewayClient":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
