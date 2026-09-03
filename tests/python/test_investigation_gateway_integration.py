import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from tuneros.can import RawCanGatewayClient, TunerOsDbcDecoder
from tuneros.investigation import InvestigationService
from tuneros.session import SessionCatalog, SessionReader, SessionRecorder, replay_session
from tuneros.telemetry import SignalKey

_REPOSITORY_ROOT = Path(__file__).parents[2]
BATTERY = SignalKey("DmeThermalElectrical", "BatteryVoltage")
ENGINE_RUNNING = SignalKey("DmeFastEngine", "EngineRunning")
VEHICLE_SPEED = SignalKey("DscVehicleMotion", "VehicleSpeed")
FRONT_LEFT = SignalKey("DscWheelSpeeds", "FrontLeftWheelSpeed")


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


def _record_gateway_session(
    root: Path,
    name: str,
    *,
    duration_microseconds: int | None = None,
    fault: str | None = None,
) -> SessionReader:
    arguments = [str(_gateway_executable()), "--scenario", "city", "--port", "0"]
    if duration_microseconds is not None:
        arguments.extend(("--duration-us", str(duration_microseconds)))
    if fault is not None:
        arguments.extend(("--fault", fault, "--fault-at-us", "1000000"))
    process = subprocess.Popen(
        arguments,
        cwd=_REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    recorder = SessionRecorder(root, name=name, scenario="city")
    try:
        readiness = process.stdout.readline().strip()
        assert readiness.startswith("LISTENING ")
        port = int(readiness.removeprefix("LISTENING "))
        with RawCanGatewayClient.connect(port=port, timeout=10) as client:
            for frame in client.frames():
                recorder.record(frame)
        assert process.wait(timeout=10) == 0, process.stderr.read()
        recorder.complete()
        return SessionReader(recorder.artifact_path)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if recorder.recording:
            recorder.abort("gateway integration test interrupted")


@dataclass(frozen=True)
class GatewaySessions:
    catalog: SessionCatalog
    charging: SessionReader
    healthy: SessionReader
    wheel: SessionReader


@pytest.fixture(scope="module")
def gateway_sessions(tmp_path_factory: pytest.TempPathFactory) -> GatewaySessions:
    root = tmp_path_factory.mktemp("investigation-gateway")
    return GatewaySessions(
        catalog=SessionCatalog(root),
        charging=_record_gateway_session(
            root,
            "charging fault",
            duration_microseconds=8_000_000,
            fault="charging-failure",
        ),
        healthy=_record_gateway_session(
            root,
            "healthy baseline",
            duration_microseconds=8_000_000,
        ),
        wheel=_record_gateway_session(
            root,
            "wheel sensor fault",
            duration_microseconds=4_000_000,
            fault="front-left-wheel-speed-sensor-bias",
        ),
    )


def test_charging_fault_investigation_matches_normal_replay_evidence(
    gateway_sessions: GatewaySessions,
) -> None:
    service = InvestigationService(gateway_sessions.catalog)
    discovery = service.investigate(
        gateway_sessions.charging.manifest.session_id,
        center_timestamp_microseconds=4_000_000,
        before_microseconds=4_000_000,
        after_microseconds=4_000_000,
        diagnostic_code="TUN-DME-003",
    )
    confirmation = next(
        event
        for event in discovery.diagnostic_events
        if event.code == "TUN-DME-003" and event.event_type == "dtc_confirmed"
    )
    result = service.investigate(
        gateway_sessions.charging.manifest.session_id,
        center_timestamp_microseconds=confirmation.timestamp_microseconds,
        selected_signals=(BATTERY, ENGINE_RUNNING),
        diagnostic_code="TUN-DME-003",
    )
    replay = replay_session(gateway_sessions.charging, history_capacity=4_096)
    state = next(
        item for item in result.diagnostic_states_at_center if item.definition.code == "TUN-DME-003"
    )
    freeze = next(frame for frame in result.freeze_frames_at_center if frame.code == "TUN-DME-003")
    frozen = {signal.key: signal for signal in freeze.signals}

    assert confirmation.timestamp_microseconds == 4_700_000
    assert state.status == "active"
    assert state.record is not None
    assert state.record.confirmed_timestamp_microseconds == confirmation.timestamp_microseconds
    assert frozen[BATTERY].value < 12.5
    assert frozen[BATTERY].source_ecu == "TunerOsSimulatedDme"
    assert frozen[ENGINE_RUNNING].value is True
    assert any(frame.raw_frame.arbitration_id == 0x502 for frame in result.raw_frames)
    replay_dtc = replay.diagnostics.dtc("TUN-DME-003")
    assert replay_dtc is not None
    assert replay_dtc.definition.code == state.record.definition.code
    assert (
        replay_dtc.confirmed_timestamp_microseconds == state.record.confirmed_timestamp_microseconds
    )
    assert replay_dtc.occurrence_count == state.record.occurrence_count
    assert replay.diagnostics.freeze_frame("TUN-DME-003") == freeze
    assert confirmation in replay.diagnostics.events()


def test_healthy_baseline_comparison_reports_observed_charging_difference(
    gateway_sessions: GatewaySessions,
) -> None:
    comparison = InvestigationService(gateway_sessions.catalog).compare(
        gateway_sessions.charging.manifest.session_id,
        gateway_sessions.healthy.manifest.session_id,
        primary_center_timestamp_microseconds=4_700_000,
        baseline_center_timestamp_microseconds=4_700_000,
        selected_signals=(BATTERY, ENGINE_RUNNING),
        diagnostic_code="TUN-DME-003",
    )
    battery = comparison.signal_comparisons[0]

    assert battery.primary.maximum is not None and battery.primary.maximum < 12.5
    assert battery.baseline.minimum is not None and battery.baseline.minimum >= 13.0
    assert battery.mean_difference is not None and battery.mean_difference < -1.0
    assert comparison.primary_has_diagnostic_event is True
    assert comparison.baseline_has_diagnostic_event is False


def test_wheel_fault_investigation_contains_cross_ecu_evidence(
    gateway_sessions: GatewaySessions,
) -> None:
    result = InvestigationService(gateway_sessions.catalog).investigate(
        gateway_sessions.wheel.manifest.session_id,
        center_timestamp_microseconds=2_000_000,
        selected_signals=(
            VEHICLE_SPEED,
            FRONT_LEFT,
            SignalKey("DscWheelSpeeds", "FrontRightWheelSpeed"),
            SignalKey("DscWheelSpeeds", "RearLeftWheelSpeed"),
            SignalKey("DscWheelSpeeds", "RearRightWheelSpeed"),
        ),
        diagnostic_code="TUN-DSC-001",
    )
    state = next(
        item for item in result.diagnostic_states_at_center if item.definition.code == "TUN-DSC-001"
    )
    freeze = next(frame for frame in result.freeze_frames_at_center if frame.code == "TUN-DSC-001")
    frozen = {signal.key: signal for signal in freeze.signals}

    assert state.status == "active"
    assert frozen[FRONT_LEFT].value - frozen[VEHICLE_SPEED].value > 3.0
    assert frozen[FRONT_LEFT].source_ecu == "TunerOsSimulatedDsc"
    assert {frame.raw_frame.arbitration_id for frame in result.raw_frames} >= {0x520, 0x521}
    for key in result.selected_signals[2:]:
        assert frozen[key].value == pytest.approx(frozen[VEHICLE_SPEED].value, abs=0.01)


def test_default_city_investigation_is_bounded_and_preserves_regression_counts(
    tmp_path: Path,
) -> None:
    reader = _record_gateway_session(tmp_path, "full city")
    result = InvestigationService(SessionCatalog(tmp_path)).investigate(
        reader.manifest.session_id,
        center_timestamp_microseconds=52_500_000,
    )
    decoder = TunerOsDbcDecoder()
    signal_updates = sum(len(decoder.decode(frame).signals) for frame in reader.frames())

    assert reader.manifest.frame_count == 27_305
    assert signal_updates == 93_467
    assert result.window.duration_microseconds == 4_000_000
    assert 1_000 < result.statistics.raw_frame_count < 1_100
    assert result.statistics.raw_frame_count < reader.manifest.frame_count
