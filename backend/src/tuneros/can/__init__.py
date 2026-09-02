"""Raw CAN and DBC decode boundary for TunerOS."""

from tuneros.can.decoder import (
    CanDecodeError,
    MalformedCanFrameError,
    TunerOsDbcDecoder,
    UnknownCanFrameError,
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

__all__ = [
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
    "RawCanGatewayClient",
    "SignalValue",
    "TunerOsDbcDecoder",
    "UnknownCanFrameError",
    "decode_gateway_header",
    "decode_gateway_record",
]
