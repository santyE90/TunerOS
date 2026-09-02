"""Thread-safe application coordination for the live decoded telemetry pipeline."""

import asyncio
import math
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from tuneros.can import (
    DEFAULT_GATEWAY_HOST,
    DEFAULT_GATEWAY_PORT,
    DecodedCanFrame,
    RawCanFrame,
    RawCanGatewayClient,
    TunerOsDbcDecoder,
)
from tuneros.telemetry.catalog import SignalCatalog
from tuneros.telemetry.engine import DEFAULT_HISTORY_CAPACITY, TelemetryEngine
from tuneros.telemetry.models import (
    SignalFreshness,
    SignalKey,
    SignalSample,
    TelemetrySchemaError,
    TelemetrySnapshot,
    TelemetryStatistics,
)

DEFAULT_SUBSCRIBER_QUEUE_CAPACITY = 256
DEFAULT_GATEWAY_CONNECT_TIMEOUT_SECONDS = 10.0
SERVICE_STOP_TIMEOUT_SECONDS = 5.0


class TelemetryServiceState(StrEnum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TelemetryServiceConfig:
    gateway_host: str = DEFAULT_GATEWAY_HOST
    gateway_port: int = DEFAULT_GATEWAY_PORT
    history_capacity: int = DEFAULT_HISTORY_CAPACITY
    subscriber_queue_capacity: int = DEFAULT_SUBSCRIBER_QUEUE_CAPACITY
    gateway_connect_timeout_seconds: float = DEFAULT_GATEWAY_CONNECT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.gateway_host, str):
            raise TypeError("gateway_host must be a string")
        if not self.gateway_host:
            raise ValueError("gateway_host cannot be empty")
        self._validate_positive_integer("gateway_port", self.gateway_port, maximum=65_535)
        self._validate_positive_integer("history_capacity", self.history_capacity)
        self._validate_positive_integer("subscriber_queue_capacity", self.subscriber_queue_capacity)
        if (
            isinstance(self.gateway_connect_timeout_seconds, bool)
            or not isinstance(self.gateway_connect_timeout_seconds, (int, float))
            or not math.isfinite(self.gateway_connect_timeout_seconds)
            or self.gateway_connect_timeout_seconds <= 0
        ):
            raise ValueError("gateway_connect_timeout_seconds must be positive")

    @staticmethod
    def _validate_positive_integer(name: str, value: int, *, maximum: int | None = None) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
        if value <= 0 or (maximum is not None and value > maximum):
            suffix = f" in [1, {maximum}]" if maximum is not None else " positive"
            raise ValueError(f"{name} must be{suffix}")


@dataclass(frozen=True, slots=True)
class TelemetryUpdate:
    timestamp_microseconds: int
    frame_sequence: int
    arbitration_id: int
    message_name: str
    source_ecu: str
    samples: tuple[SignalSample, ...]
    freshness: tuple[SignalFreshness, ...]


@dataclass(frozen=True, slots=True)
class TelemetryServiceStateUpdate:
    state: TelemetryServiceState
    error: str | None = None


type TelemetryServiceEvent = TelemetryUpdate | TelemetryServiceStateUpdate


@dataclass(frozen=True, slots=True)
class SubscriberClosed:
    reason: str


type SubscriberItem = TelemetryServiceEvent | SubscriberClosed


class GatewayStream(Protocol):
    def frames(self) -> Iterator[RawCanFrame]: ...

    def close(self) -> None: ...


type GatewayConnector = Callable[..., GatewayStream]


class TelemetrySubscription:
    """One bounded async event stream owned by a WebSocket client."""

    def __init__(
        self,
        broadcaster: "TelemetryBroadcaster",
        loop: asyncio.AbstractEventLoop,
        capacity: int,
    ) -> None:
        self._broadcaster = broadcaster
        self._loop = loop
        self._capacity = capacity
        self._queue: asyncio.Queue[SubscriberItem] = asyncio.Queue(maxsize=capacity)
        self._state_lock = threading.Lock()
        self._active = True
        self._outstanding_deliveries = 0

    @property
    def active(self) -> bool:
        with self._state_lock:
            return self._active

    async def receive(self) -> SubscriberItem:
        item = await self._queue.get()
        if not isinstance(item, SubscriberClosed):
            with self._state_lock:
                if self._active:
                    self._outstanding_deliveries -= 1
        return item

    def close(self) -> None:
        self._broadcaster.unsubscribe(self)

    def _schedule(self, event: TelemetryServiceEvent) -> None:
        with self._state_lock:
            if not self._active:
                return
            if self._outstanding_deliveries >= self._capacity:
                overflow = True
            else:
                self._outstanding_deliveries += 1
                overflow = False
        if overflow:
            self._broadcaster.disconnect_slow_subscriber(self)
            return
        try:
            self._loop.call_soon_threadsafe(self._deliver, event)
        except RuntimeError:
            self._broadcaster.unsubscribe(self)

    def _deliver(self, event: TelemetryServiceEvent) -> None:
        if not self.active:
            return
        self._queue.put_nowait(event)

    def _deactivate(self, reason: str | None = None) -> None:
        with self._state_lock:
            if not self._active:
                return
            self._active = False
            self._outstanding_deliveries = 0
        if reason is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._deliver_closed, reason)
        except RuntimeError:
            return

    def _deliver_closed(self, reason: str) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()
        self._queue.put_nowait(SubscriberClosed(reason))


class TelemetryBroadcaster:
    """Small thread-safe broadcaster with one bounded queue per subscriber."""

    def __init__(self, queue_capacity: int) -> None:
        self._queue_capacity = queue_capacity
        self._lock = threading.Lock()
        self._subscriptions: set[TelemetrySubscription] = set()

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    def subscribe(self, loop: asyncio.AbstractEventLoop) -> TelemetrySubscription:
        subscription = TelemetrySubscription(self, loop, self._queue_capacity)
        with self._lock:
            self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription: TelemetrySubscription) -> None:
        with self._lock:
            self._subscriptions.discard(subscription)
            subscription._deactivate()

    def disconnect_slow_subscriber(self, subscription: TelemetrySubscription) -> None:
        with self._lock:
            if subscription not in self._subscriptions:
                return
            self._subscriptions.remove(subscription)
            subscription._deactivate("slow_client")

    def publish(self, event: TelemetryServiceEvent) -> None:
        with self._lock:
            subscriptions = tuple(self._subscriptions)
        for subscription in subscriptions:
            subscription._schedule(event)


@dataclass(frozen=True, slots=True)
class TelemetryServiceStatus:
    state: TelemetryServiceState
    last_error: str | None
    statistics: TelemetryStatistics

    @property
    def gateway_connected(self) -> bool:
        return self.state is TelemetryServiceState.RUNNING


class TelemetryService:
    """Own the gateway/decoder/engine pipeline and expose synchronized domain reads."""

    def __init__(
        self,
        config: TelemetryServiceConfig | None = None,
        *,
        decoder: TunerOsDbcDecoder | None = None,
        engine: TelemetryEngine | None = None,
        gateway_connector: GatewayConnector = RawCanGatewayClient.connect,
    ) -> None:
        self._config = config or TelemetryServiceConfig()
        self._decoder = decoder or TunerOsDbcDecoder()
        self._engine = engine or TelemetryEngine(
            SignalCatalog(self._decoder.database_metadata), self._config.history_capacity
        )
        if engine is not None and engine.history_capacity != self._config.history_capacity:
            raise ValueError("injected engine history capacity must match service configuration")
        self._gateway_connector = gateway_connector
        self._broadcaster = TelemetryBroadcaster(self._config.subscriber_queue_capacity)
        self._lock = threading.RLock()
        self._state_changed = threading.Condition(self._lock)
        self._state = TelemetryServiceState.STOPPED
        self._state_transitions = [self._state]
        self._last_error: str | None = None
        self._worker: threading.Thread | None = None
        self._client: GatewayStream | None = None
        self._stop_requested = threading.Event()
        self._started_once = False

    @property
    def config(self) -> TelemetryServiceConfig:
        return self._config

    @property
    def catalog(self) -> SignalCatalog:
        return self._engine.catalog

    @property
    def state(self) -> TelemetryServiceState:
        with self._lock:
            return self._state

    @property
    def state_transitions(self) -> tuple[TelemetryServiceState, ...]:
        with self._lock:
            return tuple(self._state_transitions)

    @property
    def subscriber_count(self) -> int:
        return self._broadcaster.subscriber_count

    def start(self) -> None:
        with self._lock:
            if self._started_once:
                raise RuntimeError("TelemetryService instances cannot be restarted")
            self._started_once = True
            self._stop_requested.clear()
            self._transition_locked(TelemetryServiceState.CONNECTING)
            self._worker = threading.Thread(
                target=self._run_gateway,
                name="tuneros-telemetry-gateway",
                daemon=True,
            )
            self._worker.start()

    def stop(self) -> None:
        self._stop_requested.set()
        with self._lock:
            client = self._client
            worker = self._worker
        if client is not None:
            client.close()
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=SERVICE_STOP_TIMEOUT_SECONDS)
            if worker.is_alive():
                raise RuntimeError("telemetry gateway worker did not stop within timeout")
        with self._lock:
            self._client = None
            self._worker = None
            if self._state is not TelemetryServiceState.STOPPED:
                self._transition_locked(TelemetryServiceState.STOPPED)

    def wait_for_state(
        self, expected: TelemetryServiceState, *, timeout: float = SERVICE_STOP_TIMEOUT_SECONDS
    ) -> bool:
        with self._state_changed:
            return self._state_changed.wait_for(
                lambda: expected in self._state_transitions, timeout=timeout
            )

    def ingest_decoded(self, frame: DecodedCanFrame) -> TelemetryUpdate:
        if not frame.signals:
            raise TelemetrySchemaError("decoded telemetry frames must contain at least one signal")
        with self._lock:
            samples = self._engine.ingest(frame)
            freshness: list[SignalFreshness] = []
            for sample in samples:
                status = self._engine.freshness(sample.key)
                if status is None:  # pragma: no cover - sample was just ingested
                    raise AssertionError("an accepted telemetry sample must have freshness")
                freshness.append(status)
            update = TelemetryUpdate(
                timestamp_microseconds=frame.timestamp_microseconds,
                frame_sequence=samples[0].frame_sequence,
                arbitration_id=frame.arbitration_id,
                message_name=frame.message_name,
                source_ecu=samples[0].source_ecu,
                samples=samples,
                freshness=tuple(freshness),
            )
            self._broadcaster.publish(update)
            return update

    def status(self) -> TelemetryServiceStatus:
        with self._lock:
            return TelemetryServiceStatus(
                state=self._state,
                last_error=self._last_error,
                statistics=self._engine.statistics(),
            )

    def snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            return self._engine.snapshot()

    def latest(self, key: SignalKey) -> tuple[SignalSample | None, SignalFreshness | None]:
        with self._lock:
            return self._engine.latest(key), self._engine.freshness(key)

    def history(self, key: SignalKey, limit: int | None = None) -> tuple[SignalSample, ...]:
        with self._lock:
            history = self._engine.history(key)
        return history if limit is None else history[-limit:]

    def statistics(self) -> TelemetryStatistics:
        with self._lock:
            return self._engine.statistics()

    def subscribe(
        self, loop: asyncio.AbstractEventLoop
    ) -> tuple[TelemetrySubscription, TelemetrySnapshot, TelemetryServiceStatus]:
        with self._lock:
            subscription = self._broadcaster.subscribe(loop)
            return subscription, self._engine.snapshot(), self.status()

    def _run_gateway(self) -> None:
        client: GatewayStream | None = None
        try:
            client = self._gateway_connector(
                host=self._config.gateway_host,
                port=self._config.gateway_port,
                timeout=self._config.gateway_connect_timeout_seconds,
            )
            with self._lock:
                self._client = client
                if self._stop_requested.is_set():
                    return
                self._transition_locked(TelemetryServiceState.RUNNING)
            for raw_frame in client.frames():
                if self._stop_requested.is_set():
                    return
                self.ingest_decoded(self._decoder.decode(raw_frame))
            with self._lock:
                if not self._stop_requested.is_set():
                    self._transition_locked(TelemetryServiceState.COMPLETED)
        except Exception as error:
            with self._lock:
                if not self._stop_requested.is_set():
                    self._transition_locked(TelemetryServiceState.FAILED, str(error))
        finally:
            if client is not None:
                client.close()
            with self._lock:
                self._client = None

    def _transition_locked(self, state: TelemetryServiceState, error: str | None = None) -> None:
        self._state = state
        self._last_error = error
        self._state_transitions.append(state)
        self._state_changed.notify_all()
        self._broadcaster.publish(TelemetryServiceStateUpdate(state, error))
