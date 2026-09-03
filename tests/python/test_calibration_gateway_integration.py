import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from tuneros.can import RawCanFrame, RawCanGatewayClient, TunerOsDbcDecoder
from tuneros.diagnostics import DiagnosticEngine, create_default_diagnostic_catalog
from tuneros.investigation import InvestigationService
from tuneros.session import SessionCatalog, SessionReader, SessionRecorder, replay_session
from tuneros.telemetry import SignalCatalog, SignalKey, TelemetryEngine

_ROOT = Path(__file__).parents[2]
MAP = SignalKey("DmeAirLoad", "ManifoldPressureAbsolute")
LAMBDA = SignalKey("DmeCombustionObservation", "Lambda")
IGNITION = SignalKey("DmeCombustionObservation", "IgnitionTiming")
SPEED = SignalKey("DscVehicleMotion", "VehicleSpeed")
RPM = SignalKey("DmeFastEngine", "EngineSpeedRpm")
IAT = SignalKey("DmeThermalElectrical", "IntakeAirTemperature")


def _gateway() -> Path:
    configured = os.environ.get("TUNEROS_GATEWAY_SIM")
    candidates = (
        Path(configured) if configured else None,
        _ROOT / "build" / "cpp" / "can" / "Debug" / "tuneros_gateway_sim.exe",
        _ROOT / "build" / "cpp" / "can" / "tuneros_gateway_sim",
    )
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    pytest.skip("built C++ gateway not found; set TUNEROS_GATEWAY_SIM or build Debug")


@dataclass(frozen=True)
class RecordedPull:
    reader: SessionReader
    raw_frames: tuple[RawCanFrame, ...]
    live_snapshot: object
    live_statistics: object
    live_diagnostics: object
    live_histories: dict[SignalKey, object]


def _record_pull(
    root: Path, name: str, calibration: str, *, charging_fault: bool = False
) -> RecordedPull:
    arguments = [
        str(_gateway()),
        "--scenario",
        "wot-pull",
        "--calibration",
        calibration,
        "--port",
        "0",
    ]
    if charging_fault:
        arguments.extend(("--fault", "charging-failure", "--fault-at-us", "1000000"))
    process = subprocess.Popen(
        arguments,
        cwd=_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    recorder = SessionRecorder(
        root,
        name=name,
        scenario="wot-pull",
        calibration_id=calibration,
        calibration_revision=1,
    )
    decoder = TunerOsDbcDecoder()
    telemetry = TelemetryEngine(SignalCatalog(decoder.database_metadata), history_capacity=4_096)
    diagnostics = DiagnosticEngine(create_default_diagnostic_catalog(telemetry.catalog))
    raw_frames: list[RawCanFrame] = []
    try:
        readiness = process.stdout.readline().strip()
        assert readiness.startswith("LISTENING "), process.stderr.read()
        port = int(readiness.removeprefix("LISTENING "))
        with RawCanGatewayClient.connect(port=port, timeout=10) as client:
            for frame in client.frames():
                raw_frames.append(frame)
                recorder.record(frame)
                telemetry.ingest(decoder.decode(frame))
                diagnostics.ingest(telemetry.snapshot())
        assert process.wait(timeout=10) == 0, process.stderr.read()
        recorder.complete()
        return RecordedPull(
            SessionReader(recorder.artifact_path),
            tuple(raw_frames),
            telemetry.snapshot(),
            telemetry.statistics(),
            diagnostics.snapshot(),
            {key: telemetry.history(key) for key in (MAP, LAMBDA, IGNITION, SPEED, RPM, IAT)},
        )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if recorder.recording:
            recorder.abort("calibration integration test interrupted")


@pytest.fixture(scope="module")
def pulls(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[RecordedPull, RecordedPull, RecordedPull]:
    root = tmp_path_factory.mktemp("calibration-gateway")
    return (
        _record_pull(root, "Stock WOT pull", "stock"),
        _record_pull(root, "Stage 1 WOT pull", "stage-1"),
        _record_pull(root, "Stage 1 charging fault", "stage-1", charging_fault=True),
    )


def test_stock_and_stage1_record_replay_exactly_and_remain_diagnostically_clean(
    pulls: tuple[RecordedPull, RecordedPull, RecordedPull],
) -> None:
    stock, stage1, _ = pulls
    for pull, profile_id in ((stock, "stock"), (stage1, "stage-1")):
        replay = replay_session(pull.reader, history_capacity=4_096)
        assert pull.reader.manifest.format_version == 2
        assert pull.reader.manifest.calibration_id == profile_id
        assert pull.reader.manifest.calibration_revision == 1
        assert tuple(pull.reader.frames()) == pull.raw_frames
        assert replay.snapshot == pull.live_snapshot
        assert replay.statistics == pull.live_statistics
        assert replay.diagnostics.snapshot() == pull.live_diagnostics
        replay_histories = {key: replay.engine.history(key) for key in pull.live_histories}
        assert replay_histories == pull.live_histories
        assert replay.diagnostics.dtcs() == ()
        assert any(frame.arbitration_id == 0x503 for frame in pull.reader.frames())


def test_stage1_vs_stock_investigation_reports_calibration_driven_differences(
    pulls: tuple[RecordedPull, RecordedPull, RecordedPull],
) -> None:
    stock, stage1, _ = pulls
    comparison = InvestigationService(SessionCatalog(stock.reader.artifact_path.parent)).compare(
        stage1.reader.manifest.session_id,
        stock.reader.manifest.session_id,
        primary_center_timestamp_microseconds=7_000_000,
        baseline_center_timestamp_microseconds=7_000_000,
        before_microseconds=4_000_000,
        after_microseconds=3_000_000,
        selected_signals=(MAP, LAMBDA, IGNITION, SPEED, RPM, IAT),
    )
    summaries = {item.key: item for item in comparison.signal_comparisons}

    assert comparison.primary.session.calibration_id == "stage-1"
    assert comparison.baseline.session.calibration_id == "stock"
    assert summaries[MAP].mean_difference is not None and summaries[MAP].mean_difference > 10.0
    assert (
        summaries[LAMBDA].mean_difference is not None and summaries[LAMBDA].mean_difference < -0.01
    )
    assert summaries[IGNITION].mean_difference not in (None, 0.0)
    assert summaries[SPEED].primary.last > summaries[SPEED].baseline.last
    assert summaries[IAT].mean_difference is not None and summaries[IAT].mean_difference > 0.0
    assert {frame.raw_frame.arbitration_id for frame in comparison.primary.raw_frames} >= {
        0x501,
        0x503,
        0x520,
    }


def test_stage1_charging_fault_preserves_existing_diagnostic_behavior(
    pulls: tuple[RecordedPull, RecordedPull, RecordedPull],
) -> None:
    _, _, faulty = pulls
    replay = replay_session(faulty.reader, history_capacity=4_096)
    charging = replay.diagnostics.dtc("TUN-DME-003")

    assert charging is not None
    assert charging.status == "active"
    assert charging.confirmed_timestamp_microseconds == 4_700_000
    assert replay.diagnostics.freeze_frame("TUN-DME-003") is not None


def test_gateway_rejects_unknown_calibration_before_listening() -> None:
    result = subprocess.run(
        [str(_gateway()), "--calibration", "unknown"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1
    assert "--calibration must be one of: stock, stage-1" in result.stderr
    assert "LISTENING" not in result.stdout
