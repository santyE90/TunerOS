"""Raw CAN and DBC decode boundary for TunerOS."""

from tuneros.can.decoder import (
    AUTHORITATIVE_DBC_NAME,
    CanDecodeError,
    MalformedCanFrameError,
    TunerOsDbcDecoder,
    UnknownCanFrameError,
    authoritative_dbc_sha256,
)
from tuneros.can.gateway import (
    DEFAULT_GATEWAY_HOST,
    DEFAULT_GATEWAY_PORT,
    GATEWAY_HEADER_SIZE,
    GATEWAY_MAGIC,
    GATEWAY_PROTOCOL_VERSION,
    GATEWAY_RECORD_SIZE,
    GatewayConnectionError,
    GatewayError,
    GatewayProtocolError,
    RawCanGatewayClient,
    decode_gateway_header,
    decode_gateway_record,
)
from tuneros.can.metadata import CanDatabaseMetadata, CanMessageMetadata, CanSignalMetadata
from tuneros.can.models import DecodedCanFrame, RawCanFrame, SignalValue
from tuneros.can.record_codec import (
    RAW_CAN_RECORD_SIZE,
    RawCanRecordError,
    decode_raw_can_record,
    encode_raw_can_record,
)

__all__ = [
    "AUTHORITATIVE_DBC_NAME",
    "CanDecodeError",
    "CanDatabaseMetadata",
    "CanMessageMetadata",
    "CanSignalMetadata",
    "DEFAULT_GATEWAY_HOST",
    "DEFAULT_GATEWAY_PORT",
    "DecodedCanFrame",
    "GATEWAY_HEADER_SIZE",
    "GATEWAY_MAGIC",
    "GATEWAY_PROTOCOL_VERSION",
    "GATEWAY_RECORD_SIZE",
    "GatewayConnectionError",
    "GatewayError",
    "GatewayProtocolError",
    "MalformedCanFrameError",
    "RawCanFrame",
    "RAW_CAN_RECORD_SIZE",
    "RawCanRecordError",
    "RawCanGatewayClient",
    "SignalValue",
    "TunerOsDbcDecoder",
    "UnknownCanFrameError",
    "authoritative_dbc_sha256",
    "decode_gateway_header",
    "decode_gateway_record",
    "decode_raw_can_record",
    "encode_raw_can_record",
]
