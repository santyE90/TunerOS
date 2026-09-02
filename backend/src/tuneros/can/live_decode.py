"""Minimal developer consumer for the synthetic live TunerOS CAN stream."""

import argparse

from tuneros.can.decoder import TunerOsDbcDecoder
from tuneros.can.gateway import (
    DEFAULT_GATEWAY_HOST,
    DEFAULT_GATEWAY_PORT,
    RawCanGatewayClient,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Decode the synthetic TunerOS localhost raw-CAN gateway (not BMW CAN data)."
    )
    parser.add_argument("--host", default=DEFAULT_GATEWAY_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_GATEWAY_PORT)
    arguments = parser.parse_args()

    decoder = TunerOsDbcDecoder()
    with RawCanGatewayClient.connect(arguments.host, arguments.port) as client:
        for raw_frame in client.frames():
            decoded = decoder.decode(raw_frame)
            signals = " ".join(f"{name}={value}" for name, value in decoded.signals.items())
            print(
                f"[{decoded.timestamp_microseconds / 1_000_000:10.6f}s] "
                f"0x{decoded.arbitration_id:03X} {decoded.message_name} {signals}"
            )


if __name__ == "__main__":
    main()
