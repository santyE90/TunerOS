"""Run the local TunerOS telemetry API."""

import argparse
import os
from pathlib import Path

import uvicorn

from tuneros.api import DEFAULT_API_HOST, DEFAULT_API_PORT, create_app
from tuneros.can import DEFAULT_CAN_EXPLORER_CAPACITY, DEFAULT_GATEWAY_HOST, DEFAULT_GATEWAY_PORT
from tuneros.diagnostics import DEFAULT_DIAGNOSTIC_EVENT_CAPACITY
from tuneros.session import DEFAULT_SESSION_ROOT, SessionCatalog, SessionRecorder
from tuneros.telemetry import (
    DEFAULT_CAN_REPLAY_SUBSCRIBER_QUEUE_CAPACITY,
    DEFAULT_CAN_SUBSCRIBER_QUEUE_CAPACITY,
    DEFAULT_HISTORY_CAPACITY,
    DEFAULT_REPLAY_SUBSCRIBER_QUEUE_CAPACITY,
    DEFAULT_SUBSCRIBER_QUEUE_CAPACITY,
    TelemetryServiceConfig,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve live or replayed TunerOS telemetry")
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
    parser.add_argument(
        "--replay-subscriber-queue-capacity",
        type=int,
        default=DEFAULT_REPLAY_SUBSCRIBER_QUEUE_CAPACITY,
    )
    parser.add_argument("--can-explorer-capacity", type=int, default=DEFAULT_CAN_EXPLORER_CAPACITY)
    parser.add_argument(
        "--can-subscriber-queue-capacity",
        type=int,
        default=DEFAULT_CAN_SUBSCRIBER_QUEUE_CAPACITY,
    )
    parser.add_argument(
        "--can-replay-subscriber-queue-capacity",
        type=int,
        default=DEFAULT_CAN_REPLAY_SUBSCRIBER_QUEUE_CAPACITY,
    )
    parser.add_argument(
        "--diagnostic-event-capacity", type=int, default=DEFAULT_DIAGNOSTIC_EVENT_CAPACITY
    )
    parser.add_argument(
        "--session-root",
        type=Path,
        default=Path(os.environ.get("TUNEROS_SESSION_ROOT", DEFAULT_SESSION_ROOT)),
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--record-session", action="store_true")
    source.add_argument("--replay-session", metavar="SESSION_UUID")
    parser.add_argument("--session-name")
    parser.add_argument("--scenario", help="Optional recording metadata; not inferred from CAN")
    parser.add_argument(
        "--calibration",
        choices=("stock", "stage-1"),
        help="Optional recording provenance; must match the separately launched simulator",
    )
    arguments = parser.parse_args()
    if arguments.calibration is not None and not arguments.record_session:
        parser.error("--calibration requires --record-session")
    config = TelemetryServiceConfig(
        gateway_host=arguments.gateway_host,
        gateway_port=arguments.gateway_port,
        history_capacity=arguments.history_capacity,
        subscriber_queue_capacity=arguments.subscriber_queue_capacity,
        replay_subscriber_queue_capacity=arguments.replay_subscriber_queue_capacity,
        can_explorer_capacity=arguments.can_explorer_capacity,
        can_subscriber_queue_capacity=arguments.can_subscriber_queue_capacity,
        can_replay_subscriber_queue_capacity=arguments.can_replay_subscriber_queue_capacity,
        diagnostic_event_capacity=arguments.diagnostic_event_capacity,
    )
    catalog = SessionCatalog(arguments.session_root)
    recorder = (
        SessionRecorder(
            arguments.session_root,
            name=arguments.session_name,
            scenario=arguments.scenario,
            calibration_id=arguments.calibration,
            calibration_revision=1 if arguments.calibration is not None else None,
        )
        if arguments.record_session
        else None
    )
    from tuneros.telemetry import TelemetryService

    service = TelemetryService(config, recorder=recorder)
    app = create_app(
        service,
        autostart=arguments.replay_session is None,
        session_catalog=catalog,
        initial_replay_session_id=arguments.replay_session,
    )
    uvicorn.run(app, host=arguments.host, port=arguments.port)


if __name__ == "__main__":
    main()
