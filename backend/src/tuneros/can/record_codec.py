"""Shared deterministic codec for one fixed-size raw Classic CAN record."""

import struct

from tuneros.can.models import RawCanFrame

RAW_CAN_RECORD_SIZE = 19
_RAW_CAN_RECORD = struct.Struct("!QHB8s")


class RawCanRecordError(ValueError):
    """Raised when fixed-record bytes violate the raw CAN contract."""


def encode_raw_can_record(frame: RawCanFrame) -> bytes:
    """Encode a frame without changing its timestamp, ID, DLC, or payload."""

    return _RAW_CAN_RECORD.pack(
        frame.timestamp_microseconds,
        frame.arbitration_id,
        frame.payload_length,
        frame.payload.ljust(8, b"\x00"),
    )


def decode_raw_can_record(data: bytes) -> RawCanFrame:
    """Decode exactly one 19-byte record into the existing RawCanFrame type."""

    if len(data) != RAW_CAN_RECORD_SIZE:
        raise RawCanRecordError(
            f"raw CAN record requires {RAW_CAN_RECORD_SIZE} bytes, got {len(data)}"
        )
    timestamp, arbitration_id, dlc, padded_payload = _RAW_CAN_RECORD.unpack(data)
    if arbitration_id > 0x7FF:
        raise RawCanRecordError(f"invalid standard CAN arbitration ID 0x{arbitration_id:X}")
    if dlc > 8:
        raise RawCanRecordError(f"invalid Classic CAN DLC {dlc}")
    return RawCanFrame(arbitration_id, padded_payload[:dlc], timestamp)
