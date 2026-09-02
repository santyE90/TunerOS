import os
import queue
import subprocess
import threading
from pathlib import Path

import pytest
from tuneros.can import RawCanGatewayClient, TunerOsDbcDecoder

_REPOSITORY_ROOT = Path(__file__).parents[2]


def _gateway_executable() -> Path:
    configured = os.environ.get("TUNEROS_GATEWAY_SIM")
    candidates = [
        Path(configured) if configured else None,
        _REPOSITORY_ROOT / "build" / "cpp" / "can" / "Debug" / "tuneros_gateway_sim.exe",
        _REPOSITORY_ROOT / "build" / "cpp" / "can" / "tuneros_gateway_sim",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    pytest.skip("built C++ gateway not found; set TUNEROS_GATEWAY_SIM or build the Debug target")


def _readline(stream, result: queue.Queue[str]) -> None:
    result.put(stream.readline())


def test_cpp_cold_start_streams_raw_can_into_existing_python_dbc_decoder() -> None:
    executable = _gateway_executable()
    process = subprocess.Popen(
        [
            str(executable),
            "--scenario",
            "cold-start",
            "--port",
            "0",
            "--step-us",
            "10000",
            "--duration-us",
            "2000000",
        ],
        cwd=_REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    readiness: queue.Queue[str] = queue.Queue()
    reader = threading.Thread(target=_readline, args=(process.stdout, readiness), daemon=True)
    reader.start()

    try:
        line = readiness.get(timeout=10).strip()
        assert line.startswith("LISTENING ")
        port = int(line.removeprefix("LISTENING "))

        with RawCanGatewayClient.connect(port=port, timeout=10) as client:
            raw_frames = list(client.frames())

        return_code = process.wait(timeout=10)
        error_output = process.stderr.read()
        assert return_code == 0, error_output
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert len(raw_frames) == 323
    assert [frame.arbitration_id for frame in raw_frames[:3]] == [0x500, 0x501, 0x502]
    assert [frame.timestamp_microseconds for frame in raw_frames[:3]] == [0, 0, 0]
    assert [frame.payload.hex() for frame in raw_frames[:3]] == [
        "0000000000",
        "f5030000",
        "b004b004b0047e",
    ]
    expected_order = []
    for timestamp in range(0, 2_000_001, 10_000):
        expected_order.append((timestamp, 0x500, 5))
        if timestamp % 20_000 == 0:
            expected_order.append((timestamp, 0x501, 4))
        if timestamp % 100_000 == 0:
            expected_order.append((timestamp, 0x502, 7))
    assert [
        (frame.timestamp_microseconds, frame.arbitration_id, frame.payload_length)
        for frame in raw_frames
    ] == expected_order
    assert raw_frames[-1].timestamp_microseconds == 2_000_000

    decoder = TunerOsDbcDecoder()
    initial = [decoder.decode(frame) for frame in raw_frames[:3]]
    assert initial[0].message_name == "DmeFastEngine"
    assert initial[0].signals["EngineSpeedRpm"] == 0.0
    assert initial[0].signals["EngineRunning"] is False

    start_frame = next(
        frame
        for frame in raw_frames
        if frame.arbitration_id == 0x500 and frame.timestamp_microseconds == 1_000_000
    )
    later_frame = next(
        frame
        for frame in raw_frames
        if frame.arbitration_id == 0x500 and frame.timestamp_microseconds == 2_000_000
    )
    decoded_start = decoder.decode(start_frame)
    decoded_later = decoder.decode(later_frame)
    assert decoded_start.signals["EngineRunning"] is True
    assert decoded_start.signals["EngineSpeedRpm"] > 0.0
    assert decoded_later.signals["EngineSpeedRpm"] > decoded_start.signals["EngineSpeedRpm"]


@pytest.mark.parametrize(
    "arguments,expected",
    [
        (["--scenario", "highway"], "--scenario must be one of"),
        (["--port", "70000"], "--port must be in"),
        (["--step-us", "0"], "--step-us must be positive"),
    ],
)
def test_gateway_executable_rejects_invalid_cli(arguments: list[str], expected: str) -> None:
    result = subprocess.run(
        [str(_gateway_executable()), *arguments],
        cwd=_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert expected in result.stderr
