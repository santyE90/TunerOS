"""Thread-safe application coordination for the live decoded telemetry pipeline."""

import asyncio
import math
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from tuneros.can import (
    DEFAULT_CAN_EXPLORER_CAPACITY,
    DEFAULT_GATEWAY_HOST,
    DEFAULT_GATEWAY_PORT,
    CanExplorer,
    CanExplorerFrame,
    CanExplorerSnapshot,
    CanExplorerStatistics,
    CanMessageStatistics,
    DecodedCanFrame,
    RawCanFrame,
    RawCanGatewayClient,
    TunerOsDbcDecoder,
)
from tuneros.diagnostics import (
    DEFAULT_DIAGNOSTIC_EVENT_CAPACITY,
    DiagnosticCatalog,
    DiagnosticEngine,
    DiagnosticEvent,
    DiagnosticFreezeFrame,
    DiagnosticSnapshot,
    DiagnosticStatus,
    DiagnosticTroubleCode,
    create_default_diagnostic_catalog,
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
DEFAULT_REPLAY_SUBSCRIBER_QUEUE_CAPACITY = 65_536
DEFAULT_CAN_SUBSCRIBER_QUEUE_CAPACITY = 32_768
DEFAULT_CAN_REPLAY_SUBSCRIBER_QUEUE_CAPACITY = 65_536
DEFAULT_GATEWAY_CONNECT_TIMEOUT_SECONDS = 10.0
SERVICE_STOP_TIMEOUT_SECONDS = 5.0


class TelemetryServiceState(StrEnum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TelemetrySourceMode(StrEnum):
    LIVE = "live"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class TelemetryServiceConfig:
    gateway_host: str = DEFAULT_GATEWAY_HOST
    gateway_port: int = DEFAULT_GATEWAY_PORT
    history_capacity: int = DEFAULT_HISTORY_CAPACITY
    subscriber_queue_capacity: int = DEFAULT_SUBSCRIBER_QUEUE_CAPACITY
    replay_subscriber_queue_capacity: int = DEFAULT_REPLAY_SUBSCRIBER_QUEUE_CAPACITY
    can_explorer_capacity: int = DEFAULT_CAN_EXPLORER_CAPACITY
    can_subscriber_queue_capacity: int = DEFAULT_CAN_SUBSCRIBER_QUEUE_CAPACITY
    can_replay_subscriber_queue_capacity: int = DEFAULT_CAN_REPLAY_SUBSCRIBER_QUEUE_CAPACITY
    diagnostic_event_capacity: int = DEFAULT_DIAGNOSTIC_EVENT_CAPACITY
    gateway_connect_timeout_seconds: float = DEFAULT_GATEWAY_CONNECT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.gateway_host, str):
            raise TypeError("gateway_host must be a string")
        if not self.gateway_host:
            raise ValueError("gateway_host cannot be empty")
        self._validate_positive_integer("gateway_port", self.gateway_port, maximum=65_535)
        self._validate_positive_integer("history_capacity", self.history_capacity)
        self._validate_positive_integer("subscriber_queue_capacity", self.subscriber_queue_capacity)
        self._validate_positive_integer(
            "replay_subscriber_queue_capacity", self.replay_subscriber_queue_capacity
        )
        self._validate_positive_integer("can_explorer_capacity", self.can_explorer_capacity)
        self._validate_positive_integer(
            "can_subscriber_queue_capacity", self.can_subscriber_queue_capacity
        )
        self._validate_positive_integer(
            "can_replay_subscriber_queue_capacity", self.can_replay_subscriber_queue_capacity
        )
        self._validate_positive_integer("diagnostic_event_capacity", self.diagnostic_event_capacity)
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
class CanExplorerUpdate:
    frame: CanExplorerFrame
    statistics: CanExplorerStatistics
    message_statistics: CanMessageStatistics


type CanExplorerServiceEvent = CanExplorerUpdate | TelemetryServiceStateUpdate
type ServiceEvent = TelemetryServiceEvent | CanExplorerServiceEvent


@dataclass(frozen=True, slots=True)
class SubscriberClosed:
    reason: str


type SubscriberItem = ServiceEvent | SubscriberClosed


class GatewayStream(Protocol):
    def frames(self) -> Iterator[RawCanFrame]: ...

    def close(self) -> None: ...


type GatewayConnector = Callable[..., GatewayStream]


class RawFrameRecorder(Protocol):
    @property
    def frame_count(self) -> int: ...

    @property
    def recording(self) -> bool: ...

    def record(self, frame: RawCanFrame) -> None: ...

    def complete(self): ...

    def abort(self, reason: str): ...


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

    def _schedule(self, event: ServiceEvent) -> None:
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

    def _deliver(self, event: ServiceEvent) -> None:
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

    def publish(self, event: ServiceEvent) -> None:
        with self._lock:
            subscriptions = tuple(self._subscriptions)
        for subscription in subscriptions:
            subscription._schedule(event)


@dataclass(frozen=True, slots=True)
class TelemetryServiceStatus:
    state: TelemetryServiceState
    last_error: str | None
    statistics: TelemetryStatistics
    source_mode: TelemetrySourceMode

    @property
    def gateway_connected(self) -> bool:
        return (
            self.source_mode is TelemetrySourceMode.LIVE
            and self.state is TelemetryServiceState.RUNNING
        )


@dataclass(frozen=True, slots=True)
class TelemetrySourceStatus:
    mode: TelemetrySourceMode
    session_id: str | None
    session_name: str | None
    recording: bool
    recorded_frame_count: int


class TelemetryService:
    """Own the gateway/decoder/engine pipeline and expose synchronized domain reads."""

    def __init__(
        self,
        config: TelemetryServiceConfig | None = None,
        *,
        decoder: TunerOsDbcDecoder | None = None,
        engine: TelemetryEngine | None = None,
        gateway_connector: GatewayConnector = RawCanGatewayClient.connect,
        recorder: RawFrameRecorder | None = None,
        explorer: CanExplorer | None = None,
        diagnostic_engine: DiagnosticEngine | None = None,
    ) -> None:
        self._config = config or TelemetryServiceConfig()
        self._decoder = decoder or TunerOsDbcDecoder()
        self._engine = engine or TelemetryEngine(
            SignalCatalog(self._decoder.database_metadata), self._config.history_capacity
        )
        if engine is not None and engine.history_capacity != self._config.history_capacity:
            raise ValueError("injected engine history capacity must match service configuration")
        self._gateway_connector = gateway_connector
        self._recorder = recorder
        self._explorer = explorer or CanExplorer(self._decoder, self._config.can_explorer_capacity)
        if explorer is not None and explorer.capacity != self._config.can_explorer_capacity:
            raise ValueError("injected CAN explorer capacity must match service configuration")
        if diagnostic_engine is None:
            try:
                diagnostic_catalog = create_default_diagnostic_catalog(self._engine.catalog)
            except TelemetrySchemaError:
                if engine is None:
                    raise
                diagnostic_catalog = DiagnosticCatalog((), self._engine.catalog)
            self._diagnostics = DiagnosticEngine(
                diagnostic_catalog, self._config.diagnostic_event_capacity
            )
        else:
            self._diagnostics = diagnostic_engine
        if (
            diagnostic_engine is not None
            and diagnostic_engine.event_capacity != self._config.diagnostic_event_capacity
        ):
            raise ValueError("injected diagnostic event capacity must match service configuration")
        self._broadcaster = TelemetryBroadcaster(self._config.subscriber_queue_capacity)
        self._can_broadcaster = TelemetryBroadcaster(self._config.can_subscriber_queue_capacity)
        self._lock = threading.RLock()
        self._state_changed = threading.Condition(self._lock)
        self._state = TelemetryServiceState.STOPPED
        self._state_transitions = [self._state]
        self._last_error: str | None = None
        self._worker: threading.Thread | None = None
        self._client: GatewayStream | None = None
        self._stop_requested = threading.Event()
        self._live_started_once = False
        self._source_mode = TelemetrySourceMode.LIVE
        self._source_session_id: str | None = None
        self._source_session_name: str | None = None
        self._replay_start = threading.Event()

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

    @property
    def can_subscriber_count(self) -> int:
        return self._can_broadcaster.subscriber_count

    def start(self) -> None:
        with self._lock:
            if self._live_started_once:
                raise RuntimeError("TelemetryService instances cannot be restarted")
            if self._state in (TelemetryServiceState.CONNECTING, TelemetryServiceState.RUNNING):
                raise RuntimeError("a telemetry source is already active")
            self._live_started_once = True
            self._source_mode = TelemetrySourceMode.LIVE
            self._source_session_id = None
            self._source_session_name = None
            self._explorer.reset()
            self._diagnostics.reset()
            self._stop_requested.clear()
            self._transition_locked(TelemetryServiceState.CONNECTING)
            self._worker = threading.Thread(
                target=self._run_gateway,
                name="tuneros-telemetry-gateway",
                daemon=True,
            )
            self._worker.start()

    def start_replay(
        self,
        frames: Callable[[], Iterator[RawCanFrame]],
        *,
        session_id: str,
        session_name: str | None,
        wait_for_subscriber: bool = False,
    ) -> None:
        with self._lock:
            if self._state in (TelemetryServiceState.CONNECTING, TelemetryServiceState.RUNNING):
                raise RuntimeError("a telemetry source is already active")
            if self._worker is not None and self._worker.is_alive():
                raise RuntimeError("previous telemetry source worker is still active")
            if (
                self._broadcaster.subscriber_count != 0
                or self._can_broadcaster.subscriber_count != 0
            ):
                raise RuntimeError("replay requires all previous subscribers to close")
            self._broadcaster = TelemetryBroadcaster(self._config.replay_subscriber_queue_capacity)
            self._can_broadcaster = TelemetryBroadcaster(
                self._config.can_replay_subscriber_queue_capacity
            )
            self._stop_requested.clear()
            self._engine.reset()
            self._explorer.reset()
            self._diagnostics.reset()
            self._last_error = None
            self._source_mode = TelemetrySourceMode.REPLAY
            self._source_session_id = session_id
            self._source_session_name = session_name
            self._replay_start.clear()
            if not wait_for_subscriber:
                self._replay_start.set()
            self._transition_locked(TelemetryServiceState.RUNNING)
            self._worker = threading.Thread(
                target=self._run_replay,
                args=(frames,),
                name="tuneros-telemetry-replay",
                daemon=True,
            )
            self._worker.start()

    def stop(self) -> None:
        self._stop_requested.set()
        self._replay_start.set()
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
            self._diagnostics.ingest(self._engine.snapshot())
            self._broadcaster.publish(update)
            return update

    def status(self) -> TelemetryServiceStatus:
        with self._lock:
            return TelemetryServiceStatus(
                state=self._state,
                last_error=self._last_error,
                statistics=self._engine.statistics(),
                source_mode=self._source_mode,
            )

    def source_status(self) -> TelemetrySourceStatus:
        with self._lock:
            return TelemetrySourceStatus(
                mode=self._source_mode,
                session_id=self._source_session_id,
                session_name=self._source_session_name,
                recording=self._recorder.recording if self._recorder is not None else False,
                recorded_frame_count=self._recorder.frame_count
                if self._recorder is not None
                else 0,
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

    def can_frames(
        self,
        *,
        limit: int | None = None,
        arbitration_id: int | None = None,
        message_name: str | None = None,
        source_ecu: str | None = None,
    ) -> tuple[CanExplorerFrame, ...]:
        with self._lock:
            return self._explorer.frames(
                limit=limit,
                arbitration_id=arbitration_id,
                message_name=message_name,
                source_ecu=source_ecu,
            )

    def can_frame(self, sequence: int) -> CanExplorerFrame | None:
        with self._lock:
            return self._explorer.frame(sequence)

    def can_statistics(self) -> CanExplorerStatistics:
        with self._lock:
            return self._explorer.statistics()

    def can_message_statistics(self) -> tuple[CanMessageStatistics, ...]:
        with self._lock:
            return self._explorer.message_statistics()

    def can_snapshot(self, *, frame_limit: int | None = None) -> CanExplorerSnapshot:
        with self._lock:
            return self._explorer.snapshot(frame_limit=frame_limit)

    def diagnostic_snapshot(self) -> DiagnosticSnapshot:
        with self._lock:
            return self._diagnostics.snapshot()

    def diagnostic_dtcs(
        self, status: DiagnosticStatus | None = None
    ) -> tuple[DiagnosticTroubleCode, ...]:
        with self._lock:
            return self._diagnostics.dtcs(status)

    def diagnostic_dtc(self, code: str) -> DiagnosticTroubleCode | None:
        with self._lock:
            return self._diagnostics.dtc(code)

    def diagnostic_events(self, limit: int | None = None) -> tuple[DiagnosticEvent, ...]:
        with self._lock:
            return self._diagnostics.events(limit)

    def diagnostic_freeze_frame(self, code: str) -> DiagnosticFreezeFrame | None:
        with self._lock:
            return self._diagnostics.freeze_frame(code)

    def clear_diagnostic(self, code: str) -> DiagnosticTroubleCode:
        with self._lock:
            return self._diagnostics.clear(code)

    def subscribe(
        self, loop: asyncio.AbstractEventLoop
    ) -> tuple[TelemetrySubscription, TelemetrySnapshot, TelemetryServiceStatus]:
        with self._lock:
            subscription = self._broadcaster.subscribe(loop)
            result = subscription, self._engine.snapshot(), self.status()
            if self._source_mode is TelemetrySourceMode.REPLAY:
                self._replay_start.set()
            return result

    def subscribe_can(
        self, loop: asyncio.AbstractEventLoop, *, frame_limit: int | None = None
    ) -> tuple[
        TelemetrySubscription,
        CanExplorerSnapshot,
        TelemetryServiceStatus,
        TelemetrySourceStatus,
    ]:
        with self._lock:
            subscription = self._can_broadcaster.subscribe(loop)
            result = (
                subscription,
                self._explorer.snapshot(frame_limit=frame_limit),
                self.status(),
                self.source_status(),
            )
            if self._source_mode is TelemetrySourceMode.REPLAY:
                self._replay_start.set()
            return result

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
                if self._recorder is not None:
                    self._recorder.record(raw_frame)
                self._ingest_can_explorer(raw_frame)
                self.ingest_decoded(self._decoder.decode(raw_frame))
            if self._recorder is not None:
                self._recorder.complete()
            with self._lock:
                if not self._stop_requested.is_set():
                    self._transition_locked(TelemetryServiceState.COMPLETED)
        except Exception as error:
            failure = str(error)
            if self._recorder is not None:
                try:
                    self._recorder.abort(failure)
                except Exception as recording_error:
                    failure = f"{failure}; recording finalization failed: {recording_error}"
            with self._lock:
                if not self._stop_requested.is_set():
                    self._transition_locked(TelemetryServiceState.FAILED, failure)
        finally:
            if client is not None:
                client.close()
            if self._recorder is not None and self._recorder.recording:
                reason = (
                    "recording stopped before normal gateway completion"
                    if self._stop_requested.is_set()
                    else "recording ended without normal gateway completion"
                )
                self._recorder.abort(reason)
            with self._lock:
                self._client = None

    def _run_replay(self, frames: Callable[[], Iterator[RawCanFrame]]) -> None:
        try:
            self._replay_start.wait()
            if self._stop_requested.is_set():
                return
            for raw_frame in frames():
                if self._stop_requested.is_set():
                    return
                self._ingest_can_explorer(raw_frame)
                self.ingest_decoded(self._decoder.decode(raw_frame))
            with self._lock:
                if not self._stop_requested.is_set():
                    self._transition_locked(TelemetryServiceState.COMPLETED)
        except Exception as error:
            with self._lock:
                if not self._stop_requested.is_set():
                    self._transition_locked(TelemetryServiceState.FAILED, str(error))

    def _transition_locked(self, state: TelemetryServiceState, error: str | None = None) -> None:
        self._state = state
        self._last_error = error
        self._state_transitions.append(state)
        self._state_changed.notify_all()
        update = TelemetryServiceStateUpdate(state, error)
        self._broadcaster.publish(update)
        self._can_broadcaster.publish(update)

    def _ingest_can_explorer(self, raw_frame: RawCanFrame) -> CanExplorerUpdate:
        with self._lock:
            frame = self._explorer.ingest(raw_frame)
            update = CanExplorerUpdate(
                frame=frame,
                statistics=self._explorer.statistics(),
                message_statistics=self._explorer.message_statistic(raw_frame.arbitration_id),
            )
            self._can_broadcaster.publish(update)
            return update
