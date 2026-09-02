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
            "6000000",
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
        service.stop()

        assert process.wait(timeout=10) == 0, process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    reader = SessionReader(recorder.recorder.artifact_path)
    replayed_frames = list(reader.frames())
    replay = replay_session(reader)

    assert replayed_frames == recorder.observed
    assert len(replayed_frames) == reader.manifest.frame_count == 1_565
    assert replay.snapshot == live_snapshot
    assert replay.statistics == live_statistics
    assert replay.statistics.total_signal_updates == 5_357
    for key, history in live_histories.items():
        assert replay.engine.history(key) == history
    assert (reader.artifact_path / "frames.bin").stat().st_size == 8 + 1_565 * 19
