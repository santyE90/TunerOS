"""Deterministic decoded-signal aggregation for TunerOS."""

from importlib import import_module

from tuneros.telemetry.catalog import SignalCatalog, SignalDefinition
from tuneros.telemetry.engine import DEFAULT_HISTORY_CAPACITY, TelemetryEngine
from tuneros.telemetry.models import (
    OutOfOrderTelemetryError,
    SignalFreshness,
    SignalKey,
    SignalSample,
    TelemetryError,
    TelemetrySchemaError,
    TelemetrySnapshot,
    TelemetryStatistics,
)

_SERVICE_EXPORTS = frozenset(
    {
        "DEFAULT_CAN_REPLAY_SUBSCRIBER_QUEUE_CAPACITY",
        "DEFAULT_CAN_SUBSCRIBER_QUEUE_CAPACITY",
        "DEFAULT_REPLAY_SUBSCRIBER_QUEUE_CAPACITY",
        "DEFAULT_SUBSCRIBER_QUEUE_CAPACITY",
        "CanExplorerUpdate",
        "SubscriberClosed",
        "TelemetryBroadcaster",
        "TelemetryService",
        "TelemetryServiceConfig",
        "TelemetryServiceState",
        "TelemetryServiceStateUpdate",
        "TelemetryServiceStatus",
        "TelemetrySourceMode",
        "TelemetrySourceStatus",
        "TelemetrySubscription",
        "TelemetryUpdate",
    }
)


def __getattr__(name: str):
    if name in _SERVICE_EXPORTS:
        return getattr(import_module("tuneros.telemetry.service"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_CAN_REPLAY_SUBSCRIBER_QUEUE_CAPACITY",
    "DEFAULT_CAN_SUBSCRIBER_QUEUE_CAPACITY",
    "DEFAULT_HISTORY_CAPACITY",
    "DEFAULT_REPLAY_SUBSCRIBER_QUEUE_CAPACITY",
    "DEFAULT_SUBSCRIBER_QUEUE_CAPACITY",
    "CanExplorerUpdate",
    "OutOfOrderTelemetryError",
    "SignalCatalog",
    "SignalDefinition",
    "SignalFreshness",
    "SignalKey",
    "SignalSample",
    "SubscriberClosed",
    "TelemetryBroadcaster",
    "TelemetryEngine",
    "TelemetryError",
    "TelemetrySchemaError",
    "TelemetrySnapshot",
    "TelemetryStatistics",
    "TelemetryService",
    "TelemetryServiceConfig",
    "TelemetryServiceState",
    "TelemetryServiceStateUpdate",
    "TelemetryServiceStatus",
    "TelemetrySourceMode",
    "TelemetrySourceStatus",
    "TelemetrySubscription",
    "TelemetryUpdate",
]
