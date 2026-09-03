import os
import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest
from tuneros.can import CanExplorer, RawCanFrame, RawCanGatewayClient, TunerOsDbcDecoder
from tuneros.diagnostics import (
    DiagnosticEngine,
    DiagnosticEvent,
    DiagnosticEventType,
    DiagnosticStatus,
    create_default_diagnostic_catalog,
)
from tuneros.session import SessionReader, SessionRecorder, replay_session
from tuneros.telemetry import (
    SignalCatalog,
    SignalKey,
    TelemetryEngine,
    TelemetryService,
    TelemetryServiceConfig,
    TelemetryServiceState,
)

_REPOSITORY_ROOT = Path(__file__).parents[2]


def _gateway_executable() -> Path:
    configured = os.environ.get("TUNEROS_GATEWAY_SIM")
    candidates = (
        Path(configured) if configured else None,
        _REPOSITORY_ROOT / "build" / "cpp" / "can" / "Debug" / "tuneros_gateway_sim.exe",
        _REPOSITORY_ROOT / "build" / "cpp" / "can" / "tuneros_gateway_sim",
    )
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    pytest.skip("built C++ gateway not found; set TUNEROS_GATEWAY_SIM or build the Debug target")


def _readline(stream, result: queue.Queue[str]) -> None:
    result.put(stream.readline())


def _start_gateway(
    fault: str,
    *,
    duration_microseconds: int,
    activation_microseconds: int = 1_000_000,
    deactivation_microseconds: int | None = None,
) -> tuple[subprocess.Popen[str], int]:
    arguments = [
        str(_gateway_executable()),
        "--scenario",
        "city",
        "--port",
        "0",
        "--duration-us",
        str(duration_microseconds),
        "--fault",
        fault,
        "--fault-at-us",
        str(activation_microseconds),
    ]
    if deactivation_microseconds is not None:
        arguments.extend(("--fault-clear-at-us", str(deactivation_microseconds)))
    process = subprocess.Popen(
        arguments,
        cwd=_REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    readiness: queue.Queue[str] = queue.Queue()
    threading.Thread(target=_readline, args=(process.stdout, readiness), daemon=True).start()
    line = readiness.get(timeout=10).strip()
    assert line.startswith("LISTENING ")
    return process, int(line.removeprefix("LISTENING "))


def _collect_gateway_frames(
    fault: str,
    *,
    duration_microseconds: int,
    activation_microseconds: int = 1_000_000,
    deactivation_microseconds: int | None = None,
) -> tuple[RawCanFrame, ...]:
    process, port = _start_gateway(
        fault,
        duration_microseconds=duration_microseconds,
        activation_microseconds=activation_microseconds,
        deactivation_microseconds=deactivation_microseconds,
    )
    assert process.stderr is not None
    try:
        with RawCanGatewayClient.connect(port=port, timeout=10) as client:
            frames = tuple(client.frames())
        assert process.wait(timeout=10) == 0, process.stderr.read()
        return frames
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


@dataclass(frozen=True)
class Analysis:
    telemetry: TelemetryEngine
    diagnostics: DiagnosticEngine
    explorer: CanExplorer
    events: tuple[DiagnosticEvent, ...]
    status_after_event: tuple[DiagnosticStatus | None, ...]


def _analyze(frames: tuple[RawCanFrame, ...]) -> Analysis:
    decoder = TunerOsDbcDecoder()
    telemetry = TelemetryEngine(SignalCatalog(decoder.database_metadata), history_capacity=65_536)
    diagnostics = DiagnosticEngine(create_default_diagnostic_catalog(telemetry.catalog))
    explorer = CanExplorer(decoder, capacity=65_536)
    events: list[DiagnosticEvent] = []
    statuses: list[DiagnosticStatus | None] = []
    for raw_frame in frames:
        explorer.ingest(raw_frame)
        telemetry.ingest(decoder.decode(raw_frame))
        for event in diagnostics.ingest(telemetry.snapshot()):
            events.append(event)
            dtc = diagnostics.dtc(event.code)
            statuses.append(None if dtc is None else dtc.status)
    return Analysis(telemetry, diagnostics, explorer, tuple(events), tuple(statuses))


@pytest.mark.parametrize(
    ("fault", "duration", "code", "key", "assert_abnormal", "can_id"),
    [
        (
            "cooling-degradation",
            35_000_000,
            "TUN-DME-001",
            SignalKey("DmeThermalElectrical", "CoolantTemperature"),
            lambda value: value > 115.0,
            0x502,
        ),
        (
            "charging-failure",
            8_000_000,
            "TUN-DME-003",
            SignalKey("DmeThermalElectrical", "BatteryVoltage"),
            lambda value: value < 12.5,
            0x502,
        ),
        (
            "map-sensor-bias",
            5_000_000,
            "TUN-DME-004",
            SignalKey("DmeAirLoad", "ManifoldPressureAbsolute"),
            lambda value: value > 250.0,
            0x501,
        ),
        (
            "front-left-wheel-speed-sensor-bias",
            4_000_000,
            "TUN-DSC-001",
            SignalKey("DscWheelSpeeds", "FrontLeftWheelSpeed"),
            lambda value: value >= 5.0,
            0x521,
        ),
    ],
)
def test_each_cpp_fault_reaches_can_telemetry_pending_active_and_freeze_frame(
    fault: str,
    duration: int,
    code: str,
    key: SignalKey,
    assert_abnormal,
    can_id: int,
) -> None:
    raw_frames = _collect_gateway_frames(fault, duration_microseconds=duration)
    analysis = _analyze(raw_frames)
    dtc = analysis.diagnostics.dtc(code)
    assert dtc is not None and dtc.status is DiagnosticStatus.ACTIVE
    assert dtc.occurrence_count == 1
    detected_index = next(
        index
        for index, event in enumerate(analysis.events)
        if event.code == code and event.event_type is DiagnosticEventType.CONDITION_DETECTED
    )
    confirmed = next(
        event
        for event in analysis.events
        if event.code == code and event.event_type is DiagnosticEventType.DTC_CONFIRMED
    )
    assert analysis.status_after_event[detected_index] is DiagnosticStatus.PENDING
    assert confirmed.timestamp_microseconds - analysis.events[
        detected_index
    ].timestamp_microseconds == (dtc.definition.confirmation_duration_microseconds)

    freeze = analysis.diagnostics.freeze_frame(code)
    assert freeze is not None
    assert freeze.capture_timestamp_microseconds == confirmed.timestamp_microseconds
    frozen = {signal.key: signal for signal in freeze.signals}
    assert assert_abnormal(frozen[key].value)
    assert frozen[key].source_ecu in {"TunerOsSimulatedDme", "TunerOsSimulatedDsc"}
    assert any(
        frame.raw_frame.arbitration_id == can_id
        and any(
            signal.signal_name == key.signal_name and assert_abnormal(signal.value)
            for signal in frame.decoded_signals
        )
        for frame in analysis.explorer.frames(arbitration_id=can_id)
    )

    if code == "TUN-DSC-001":
        speed = frozen[SignalKey("DscVehicleMotion", "VehicleSpeed")].value
        assert frozen[key].value - speed > 3.0
        for name in (
            "FrontRightWheelSpeed",
            "RearLeftWheelSpeed",
            "RearRightWheelSpeed",
        ):
            assert frozen[SignalKey("DscWheelSpeeds", name)].value == pytest.approx(speed, abs=0.01)


@pytest.mark.parametrize(
    ("fault", "deactivation", "duration", "code"),
    [
        ("charging-failure", 6_000_000, 10_000_000, "TUN-DME-003"),
        ("front-left-wheel-speed-sensor-bias", 3_000_000, 5_000_000, "TUN-DSC-001"),
    ],
)
def test_fault_removal_recovers_through_telemetry_to_historical(
    fault: str, deactivation: int, duration: int, code: str
) -> None:
    analysis = _analyze(
        _collect_gateway_frames(
            fault,
            duration_microseconds=duration,
            deactivation_microseconds=deactivation,
        )
    )
    dtc = analysis.diagnostics.dtc(code)
    assert dtc is not None and dtc.status is DiagnosticStatus.HISTORICAL
    event_types = tuple(event.event_type for event in analysis.events if event.code == code)
    assert event_types == (
        DiagnosticEventType.CONDITION_DETECTED,
        DiagnosticEventType.DTC_CONFIRMED,
        DiagnosticEventType.DTC_RECOVERED,
    )


class _ObservedRecorder:
    def __init__(self, recorder: SessionRecorder) -> None:
        self.recorder = recorder
        self.observed: list[RawCanFrame] = []

    @property
    def frame_count(self) -> int:
        return self.recorder.frame_count

    @property
    def recording(self) -> bool:
        return self.recorder.recording

    def record(self, frame: RawCanFrame) -> None:
        self.observed.append(frame)
        self.recorder.record(frame)

    def complete(self):
        return self.recorder.complete()

    def abort(self, reason: str):
        return self.recorder.abort(reason)


def test_fault_session_replay_needs_no_fault_identity_and_is_exact(tmp_path: Path) -> None:
    process, port = _start_gateway("charging-failure", duration_microseconds=8_000_000)
    assert process.stderr is not None
    recorder = _ObservedRecorder(
        SessionRecorder(tmp_path, name="synthetic charging investigation", scenario="city")
    )
    service = TelemetryService(
        TelemetryServiceConfig(gateway_port=port, history_capacity=4_096), recorder=recorder
    )
    try:
        service.start()
        assert service.wait_for_state(TelemetryServiceState.COMPLETED, timeout=10)
        assert process.wait(timeout=10) == 0, process.stderr.read()
        live_snapshot = service.snapshot()
        live_statistics = service.statistics()
        live_histories = {
            definition.key: service.history(definition.key)
            for definition in service.catalog.definitions
        }
        live_diagnostics = service.diagnostic_snapshot()
        live_events = service.diagnostic_events()
        live_freeze = service.diagnostic_freeze_frame("TUN-DME-003")
        live_can = service.can_snapshot()
        service.stop()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    reader = SessionReader(recorder.recorder.artifact_path)
    assert set(reader.manifest.to_dict()) == {
        "format_name",
        "format_version",
        "session_id",
        "created_at_utc",
        "name",
        "scenario",
        "vehicle_profile_id",
        "can_network",
        "dbc_name",
        "dbc_sha256",
        "frames_sha256",
        "status",
        "failure_reason",
        "frame_count",
        "first_timestamp_microseconds",
        "last_timestamp_microseconds",
        "duration_microseconds",
    }
    assert "fault" not in str(reader.manifest.to_dict()).lower()
    replay = replay_session(reader, history_capacity=4_096, explorer=CanExplorer(capacity=4_096))

    assert tuple(reader.frames()) == tuple(recorder.observed)
    assert replay.snapshot == live_snapshot
    assert replay.statistics == live_statistics
    assert replay.explorer.snapshot() == live_can
    assert replay.diagnostics.snapshot() == live_diagnostics
    assert replay.diagnostics.events() == live_events
    assert replay.diagnostics.freeze_frame("TUN-DME-003") == live_freeze
    assert replay.diagnostics.dtc("TUN-DME-003").status is DiagnosticStatus.ACTIVE  # type: ignore[union-attr]
    for key, history in live_histories.items():
        assert replay.engine.history(key) == history
