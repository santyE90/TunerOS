import asyncio
import threading
from collections.abc import Iterator

import pytest
from tuneros.can import DecodedCanFrame, GatewayConnectionError, RawCanFrame
from tuneros.session import SessionReader, SessionRecorder, SessionStatus
from tuneros.telemetry import (
    SubscriberClosed,
    TelemetryBroadcaster,
    TelemetryService,
    TelemetryServiceConfig,
    TelemetryServiceState,
    TelemetryServiceStateUpdate,
    TelemetrySourceMode,
    TelemetryUpdate,
)


class FakeGateway:
    def __init__(
        self,
        frames: tuple[RawCanFrame, ...] = (),
        *,
        frame_error: Exception | None = None,
    ) -> None:
        self._frames = frames
        self._frame_error = frame_error
        self.closed = False

    def frames(self) -> Iterator[RawCanFrame]:
        yield from self._frames
        if self._frame_error is not None:
            raise self._frame_error

    def close(self) -> None:
        self.closed = True


class BlockingGateway:
    def __init__(self) -> None:
        self._closed = threading.Event()

    def frames(self) -> Iterator[RawCanFrame]:
        self._closed.wait()
        return
        yield  # pragma: no cover - makes this blocking method an iterator

    def close(self) -> None:
        self._closed.set()


def _fast(timestamp: int, rpm: float = 750.0) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x500,
        "DmeFastEngine",
        timestamp,
        {
            "EngineSpeedRpm": rpm,
            "ThrottlePosition": 0.06,
            "EngineLoad": 0.18,
            "EngineRunning": True,
        },
    )


def _motion(timestamp: int, speed: float = 0.0) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x520,
        "DscVehicleMotion",
        timestamp,
        {"VehicleSpeed": speed, "CurrentGear": 1},
    )


def _thermal(timestamp: int, coolant: float = 90.0) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x502,
        "DmeThermalElectrical",
        timestamp,
        {
            "CoolantTemperature": coolant,
            "OilTemperature": 100.0,
            "IntakeAirTemperature": 30.0,
            "BatteryVoltage": 14.2,
        },
    )


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"gateway_host": ""}, ValueError),
        ({"gateway_host": 1}, TypeError),
        ({"gateway_port": 0}, ValueError),
        ({"gateway_port": True}, TypeError),
        ({"history_capacity": 0}, ValueError),
        ({"subscriber_queue_capacity": -1}, ValueError),
        ({"replay_subscriber_queue_capacity": 0}, ValueError),
        ({"can_explorer_capacity": 0}, ValueError),
        ({"can_subscriber_queue_capacity": 0}, ValueError),
        ({"can_replay_subscriber_queue_capacity": 0}, ValueError),
        ({"diagnostic_event_capacity": 0}, ValueError),
        ({"gateway_connect_timeout_seconds": 0}, ValueError),
        ({"gateway_connect_timeout_seconds": float("inf")}, ValueError),
    ],
)
def test_service_configuration_validation(
    kwargs: dict[str, object], error: type[Exception]
) -> None:
    with pytest.raises(error):
        TelemetryServiceConfig(**kwargs)


def test_service_completes_on_normal_eof_and_retains_final_state() -> None:
    raw = RawCanFrame(0x500, bytes.fromhex("b80b0f2e01"), 0)
    gateway = FakeGateway((raw,))
    service = TelemetryService(gateway_connector=lambda **_: gateway)

    service.start()
    assert service.wait_for_state(TelemetryServiceState.COMPLETED)

    assert service.state is TelemetryServiceState.COMPLETED
    assert service.state_transitions == (
        TelemetryServiceState.STOPPED,
        TelemetryServiceState.CONNECTING,
        TelemetryServiceState.RUNNING,
        TelemetryServiceState.COMPLETED,
    )
    assert service.statistics().total_frames == 1
    assert service.snapshot().observation_timestamp_microseconds == 0
    assert service.can_statistics().total_frame_count == 1
    assert service.can_frame(0).raw_frame is raw
    assert gateway.closed
    service.stop()
    assert service.state is TelemetryServiceState.STOPPED


def test_gateway_failure_is_captured_without_escaping_worker() -> None:
    def fail(**_: object) -> FakeGateway:
        raise GatewayConnectionError("test gateway unavailable")

    service = TelemetryService(gateway_connector=fail)
    service.start()
    assert service.wait_for_state(TelemetryServiceState.FAILED)

    status = service.status()
    assert status.state is TelemetryServiceState.FAILED
    assert status.last_error == "test gateway unavailable"
    assert status.statistics.total_frames == 0
    service.stop()


def test_live_recording_taps_raw_frame_before_decode_and_finalizes(tmp_path) -> None:
    raw = RawCanFrame(0x500, bytes.fromhex("b80b0f2e01"), 0)
    gateway = FakeGateway((raw,))
    recorder = SessionRecorder(tmp_path, name="recorded")
    service = TelemetryService(gateway_connector=lambda **_: gateway, recorder=recorder)

    service.start()
    assert service.wait_for_state(TelemetryServiceState.COMPLETED)

    assert recorder.manifest.status is SessionStatus.COMPLETE
    assert list(SessionReader(recorder.artifact_path).frames()) == [raw]
    assert service.statistics().total_frames == 1
    assert service.source_status().mode is TelemetrySourceMode.LIVE
    assert not service.source_status().recording
    service.stop()


def test_failed_live_recording_stays_incomplete(tmp_path) -> None:
    raw = RawCanFrame(0x500, bytes.fromhex("b80b0f2e01"), 0)
    gateway = FakeGateway((raw,), frame_error=GatewayConnectionError("stream failed"))
    recorder = SessionRecorder(tmp_path)
    service = TelemetryService(gateway_connector=lambda **_: gateway, recorder=recorder)

    service.start()
    assert service.wait_for_state(TelemetryServiceState.FAILED)

    assert recorder.manifest.status is SessionStatus.INCOMPLETE
    assert recorder.manifest.frame_count == 1
    assert not tuple(tmp_path.glob("*.tuneros"))
    service.stop()


def test_explorer_preserves_malformed_known_raw_before_telemetry_failure() -> None:
    raw = RawCanFrame(0x500, b"\x01", 0)
    service = TelemetryService(gateway_connector=lambda **_: FakeGateway((raw,)))

    service.start()
    assert service.wait_for_state(TelemetryServiceState.FAILED)

    observed = service.can_frame(0)
    assert observed is not None
    assert observed.raw_frame is raw
    assert observed.decode_status == "error"
    assert service.can_statistics().total_frame_count == 1
    assert service.statistics().total_frames == 0
    service.stop()


def test_recording_disabled_writes_nothing(tmp_path) -> None:
    gateway = FakeGateway((RawCanFrame(0x500, bytes.fromhex("b80b0f2e01"), 0),))
    service = TelemetryService(gateway_connector=lambda **_: gateway)
    service.start()
    assert service.wait_for_state(TelemetryServiceState.COMPLETED)
    assert not tuple(tmp_path.iterdir())
    service.stop()


def test_replay_resets_engine_waits_for_subscriber_and_preserves_source() -> None:
    async def exercise() -> None:
        service = TelemetryService()
        service.ingest_decoded(_fast(90_000, 900.0))
        service.ingest_decoded(_thermal(90_000, 116.0))
        assert len(service.diagnostic_dtcs()) == 1
        raw = RawCanFrame(0x500, bytes.fromhex("b80b0f2e01"), 0)
        service.start_replay(
            lambda: iter((raw,)),
            session_id="12345678-1234-5678-9234-567812345678",
            session_name="Replay test",
            wait_for_subscriber=True,
        )
        assert service.statistics().total_frames == 0
        assert service.diagnostic_dtcs() == ()
        assert service.diagnostic_events() == ()
        assert service.state is TelemetryServiceState.RUNNING

        subscription, initial, _ = service.subscribe(asyncio.get_running_loop())
        assert initial.samples == {}
        update = await subscription.receive()
        completed = await subscription.receive()
        assert isinstance(update, TelemetryUpdate)
        assert update.frame_sequence == 0
        assert completed == TelemetryServiceStateUpdate(TelemetryServiceState.COMPLETED)
        assert service.source_status().mode is TelemetrySourceMode.REPLAY
        assert service.source_status().session_name == "Replay test"
        subscription.close()
        service.stop()

    asyncio.run(exercise())


def test_can_replay_queue_overflow_disconnects_without_silent_drop() -> None:
    async def exercise() -> None:
        service = TelemetryService(TelemetryServiceConfig(can_replay_subscriber_queue_capacity=1))
        raw_frames = tuple(
            RawCanFrame(0x500, bytes.fromhex("b80b0f2e01"), timestamp)
            for timestamp in range(0, 1_000_000, 10_000)
        )
        service.start_replay(
            lambda: iter(raw_frames),
            session_id="12345678-1234-5678-9234-567812345678",
            session_name="overflow",
            wait_for_subscriber=True,
        )
        subscription, initial, _, _ = service.subscribe_can(asyncio.get_running_loop())
        assert initial.frames == ()
        assert service.wait_for_state(TelemetryServiceState.COMPLETED)
        item = await asyncio.wait_for(subscription.receive(), timeout=2)
        assert item == SubscriberClosed("slow_client")
        assert not subscription.active
        assert service.can_statistics().total_frame_count == len(raw_frames)
        service.stop()

    asyncio.run(exercise())


def test_stop_closes_gateway_and_joins_blocking_worker() -> None:
    gateway = BlockingGateway()
    service = TelemetryService(gateway_connector=lambda **_: gateway)
    service.start()
    assert service.wait_for_state(TelemetryServiceState.RUNNING)

    service.stop()

    assert service.state is TelemetryServiceState.STOPPED
    assert gateway._closed.is_set()


def test_subscribers_receive_atomic_ordered_updates_and_are_independent() -> None:
    async def exercise() -> None:
        service = TelemetryService()
        first, initial, _ = service.subscribe(asyncio.get_running_loop())
        second, _, _ = service.subscribe(asyncio.get_running_loop())
        assert initial.samples == {}

        dme = service.ingest_decoded(_fast(100))
        dsc = service.ingest_decoded(_motion(100, 1.5))
        first_events = (await first.receive(), await first.receive())
        second_events = (await second.receive(), await second.receive())

        assert first_events == second_events == (dme, dsc)
        assert isinstance(dme, TelemetryUpdate)
        assert len(dme.samples) == 4
        assert {sample.frame_sequence for sample in dme.samples} == {0}
        assert dsc.frame_sequence == 1
        assert service.subscriber_count == 2
        first.close()
        second.close()
        assert service.subscriber_count == 0

    asyncio.run(exercise())


def test_slow_subscriber_is_removed_on_bounded_queue_overflow() -> None:
    async def exercise() -> None:
        service = TelemetryService(TelemetryServiceConfig(subscriber_queue_capacity=1))
        subscription, _, _ = service.subscribe(asyncio.get_running_loop())
        service.ingest_decoded(_fast(0))
        service.ingest_decoded(_fast(10_000))
        await asyncio.sleep(0)

        closed = await subscription.receive()
        assert closed == SubscriberClosed("slow_client")
        assert not subscription.active
        assert service.subscriber_count == 0

    asyncio.run(exercise())


def test_subscriber_receives_completion_and_failure_state_events() -> None:
    async def exercise() -> None:
        broadcaster = TelemetryBroadcaster(queue_capacity=2)
        subscription = broadcaster.subscribe(asyncio.get_running_loop())
        broadcaster.publish(TelemetryServiceStateUpdate(TelemetryServiceState.COMPLETED))
        event = await subscription.receive()
        assert event == TelemetryServiceStateUpdate(TelemetryServiceState.COMPLETED)
        subscription.close()

    asyncio.run(exercise())
