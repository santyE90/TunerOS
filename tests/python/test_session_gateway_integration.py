import os
import queue
import subprocess
import threading
from pathlib import Path

import pytest
from tuneros.can import RawCanFrame
from tuneros.session import SessionReader, SessionRecorder, replay_session
from tuneros.telemetry import TelemetryService, TelemetryServiceConfig, TelemetryServiceState

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


class ObservedRecorder:
    """Test observer proving the recorder sees the exact live frame objects."""

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


def _readline(stream, result: queue.Queue[str]) -> None:
    result.put(stream.readline())


def test_real_city_recording_round_trip_and_telemetry_replay_equivalence(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [
            str(_gateway_executable()),
            "--scenario",
            "city",
            "--port",
            "0",
            "--step-us",
            "10000",
            "--duration-us",
            "105000000",
        ],
        cwd=_REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    readiness: queue.Queue[str] = queue.Queue()
    threading.Thread(target=_readline, args=(process.stdout, readiness), daemon=True).start()

    try:
        line = readiness.get(timeout=10).strip()
        assert line.startswith("LISTENING ")
        port = int(line.removeprefix("LISTENING "))
        recorder = ObservedRecorder(SessionRecorder(tmp_path, name="CITY equivalence"))
        service = TelemetryService(
            TelemetryServiceConfig(gateway_port=port),
            recorder=recorder,
        )
        service.start()
        assert service.wait_for_state(TelemetryServiceState.COMPLETED, timeout=10)
        live_snapshot = service.snapshot()
        live_statistics = service.statistics()
        live_histories = {
            definition.key: service.history(definition.key)
            for definition in service.catalog.definitions
        }
        live_can_snapshot = service.can_snapshot()
        live_diagnostic_snapshot = service.diagnostic_snapshot()
        live_diagnostic_events = service.diagnostic_events()
        service.stop()

        assert process.wait(timeout=10) == 0, process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    reader = SessionReader(recorder.recorder.artifact_path)
    replayed_frames = list(reader.frames())
    replay = replay_session(reader)
    second_replay = replay_session(reader)

    assert replayed_frames == recorder.observed
    assert len(replayed_frames) == reader.manifest.frame_count == 27_305
    assert replay.snapshot == live_snapshot
    assert replay.statistics == live_statistics
    assert replay.statistics.total_signal_updates == 93_467
    assert replay.explorer.snapshot() == live_can_snapshot
    assert replay.diagnostics.snapshot() == live_diagnostic_snapshot
    assert replay.diagnostics.events() == live_diagnostic_events
    assert second_replay.diagnostics.snapshot() == replay.diagnostics.snapshot()
    assert second_replay.diagnostics.events() == replay.diagnostics.events()
    assert replay.diagnostics.dtcs() == ()
    assert replay.diagnostics.events() == ()
    assert {
        item.arbitration_id: item.total_frame_count for item in replay.explorer.message_statistics()
    } == {
        0x500: 10_501,
        0x501: 5_251,
        0x502: 1_051,
        0x520: 5_251,
        0x521: 5_251,
    }
    for key, history in live_histories.items():
        assert replay.engine.history(key) == history
    assert replay.explorer.statistics().retained_frame_count == 4_096
    assert (reader.artifact_path / "frames.bin").stat().st_size == 8 + 27_305 * 19


def test_real_one_second_can_explorer_counts_and_simulation_time_rates() -> None:
    process = subprocess.Popen(
        [
            str(_gateway_executable()),
            "--scenario",
            "city",
            "--port",
            "0",
            "--step-us",
            "10000",
            "--duration-us",
            "1000000",
        ],
        cwd=_REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    readiness: queue.Queue[str] = queue.Queue()
    threading.Thread(target=_readline, args=(process.stdout, readiness), daemon=True).start()

    try:
        port = int(readiness.get(timeout=10).strip().removeprefix("LISTENING "))
        service = TelemetryService(TelemetryServiceConfig(gateway_port=port))
        service.start()
        assert service.wait_for_state(TelemetryServiceState.COMPLETED, timeout=10)
        assert process.wait(timeout=10) == 0, process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    messages = {item.arbitration_id: item for item in service.can_message_statistics()}
    assert service.can_statistics().total_frame_count == 265
    assert {identifier: item.total_frame_count for identifier, item in messages.items()} == {
        0x500: 101,
        0x501: 51,
        0x502: 11,
        0x520: 51,
        0x521: 51,
    }
    assert {identifier: item.observed_frequency_hz for identifier, item in messages.items()} == {
        0x500: 100.0,
        0x501: 50.0,
        0x502: 10.0,
        0x520: 50.0,
        0x521: 50.0,
    }
    initial = service.can_frames(limit=5)
    assert [item.raw_frame.arbitration_id for item in service.can_frames()[:5]] == [
        0x500,
        0x501,
        0x502,
        0x520,
        0x521,
    ]
    assert initial[-1].sequence == 264
    service.stop()
