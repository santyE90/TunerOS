"""Run the local TunerOS telemetry API."""

import argparse

import uvicorn

from tuneros.api import DEFAULT_API_HOST, DEFAULT_API_PORT, create_app
from tuneros.can import DEFAULT_GATEWAY_HOST, DEFAULT_GATEWAY_PORT
from tuneros.telemetry import (
    DEFAULT_HISTORY_CAPACITY,
    DEFAULT_SUBSCRIBER_QUEUE_CAPACITY,
    TelemetryServiceConfig,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve live decoded TunerOS telemetry")
    parser.add_argument("--host", default=DEFAULT_API_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_API_PORT)
    parser.add_argument("--gateway-host", default=DEFAULT_GATEWAY_HOST)
    parser.add_argument("--gateway-port", type=int, default=DEFAULT_GATEWAY_PORT)
    parser.add_argument("--history-capacity", type=int, default=DEFAULT_HISTORY_CAPACITY)
    parser.add_argument(
        "--subscriber-queue-capacity",
        type=int,
        default=DEFAULT_SUBSCRIBER_QUEUE_CAPACITY,
    )
    arguments = parser.parse_args()
    config = TelemetryServiceConfig(
        gateway_host=arguments.gateway_host,
        gateway_port=arguments.gateway_port,
        history_capacity=arguments.history_capacity,
        subscriber_queue_capacity=arguments.subscriber_queue_capacity,
    )
    uvicorn.run(create_app(config=config), host=arguments.host, port=arguments.port)


if __name__ == "__main__":
    main()
