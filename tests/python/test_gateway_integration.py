import os
import queue
import subprocess
import threading
from pathlib import Path

import pytest
from tuneros.can import RawCanGatewayClient, TunerOsDbcDecoder
from tuneros.telemetry import SignalCatalog, SignalKey, TelemetryEngine

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


def test_cpp_city_streams_both_ecus_into_existing_python_dbc_decoder() -> None:
    executable = _gateway_executable()
    process = subprocess.Popen(
        [
            str(executable),
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

    assert len(raw_frames) == 1_565
    assert [frame.arbitration_id for frame in raw_frames[:5]] == [
        0x500,
        0x501,
        0x502,
        0x520,
        0x521,
    ]
    assert [frame.timestamp_microseconds for frame in raw_frames[:5]] == [0, 0, 0, 0, 0]
    assert [frame.payload.hex() for frame in raw_frames[:5]] == [
        "b80b0f2e01",
        "9501001a",
        "0e06dc05e2048e",
        "000000",
        "0000000000000000",
    ]
    expected_order = []
    for timestamp in range(0, 6_000_001, 10_000):
        expected_order.append((timestamp, 0x500, 5))
        if timestamp % 20_000 == 0:
            expected_order.append((timestamp, 0x501, 4))
        if timestamp % 100_000 == 0:
            expected_order.append((timestamp, 0x502, 7))
        if timestamp % 20_000 == 0:
            expected_order.append((timestamp, 0x520, 3))
            expected_order.append((timestamp, 0x521, 8))
    assert [
        (frame.timestamp_microseconds, frame.arbitration_id, frame.payload_length)
        for frame in raw_frames
    ] == expected_order
    assert raw_frames[-1].timestamp_microseconds == 6_000_000

    decoder = TunerOsDbcDecoder()
    telemetry = TelemetryEngine(SignalCatalog(decoder.database_metadata))
    decoded_frames = [decoder.decode(frame) for frame in raw_frames]
    for decoded_frame in decoded_frames:
        telemetry.ingest(decoded_frame)

    telemetry_snapshot = telemetry.snapshot()
    telemetry_statistics = telemetry.statistics()
    rpm_key = SignalKey("DmeFastEngine", "EngineSpeedRpm")
    speed_key = SignalKey("DscVehicleMotion", "VehicleSpeed")
    gear_key = SignalKey("DscVehicleMotion", "CurrentGear")
    coolant_key = SignalKey("DmeThermalElectrical", "CoolantTemperature")
    wheel_keys = tuple(
        SignalKey("DscWheelSpeeds", name)
        for name in (
            "FrontLeftWheelSpeed",
            "FrontRightWheelSpeed",
            "RearLeftWheelSpeed",
            "RearRightWheelSpeed",
        )
    )
    required_snapshot_keys = (
        rpm_key,
        SignalKey("DmeFastEngine", "ThrottlePosition"),
        SignalKey("DmeFastEngine", "EngineLoad"),
        SignalKey("DmeFastEngine", "EngineRunning"),
        SignalKey("DmeAirLoad", "ManifoldPressureAbsolute"),
        coolant_key,
        SignalKey("DmeThermalElectrical", "BatteryVoltage"),
        speed_key,
        gear_key,
        *wheel_keys,
    )

    assert telemetry_statistics.total_frames == len(raw_frames) == 1_565
    assert telemetry_statistics.total_signal_updates == 5_357
    assert telemetry_statistics.latest_timestamp_microseconds == 6_000_000
    assert telemetry_statistics.last_frame_sequence == 1_564
    assert telemetry_snapshot.observation_timestamp_microseconds == 6_000_000
    assert telemetry_snapshot.latest(rpm_key).source_ecu == "TunerOsSimulatedDme"
    assert telemetry_snapshot.latest(rpm_key).frame_sequence == 1_560
    assert telemetry_snapshot.latest(speed_key).source_ecu == "TunerOsSimulatedDsc"
    assert telemetry_snapshot.latest(speed_key).frame_sequence == 1_563
    assert telemetry_snapshot.latest(gear_key) is not None
    assert telemetry_snapshot.latest(coolant_key).frame_sequence == 1_562
    assert all(telemetry_snapshot.latest(key) is not None for key in required_snapshot_keys)
    assert len(telemetry.history(rpm_key)) == 256
    assert len(telemetry.history(speed_key)) == 256
    assert len(telemetry.history(coolant_key)) == 61
    for wheel_key in wheel_keys:
        assert telemetry_snapshot.latest(wheel_key).frame_sequence == 1_564
        assert telemetry_snapshot.latest(wheel_key).value == pytest.approx(
            telemetry_snapshot.latest(speed_key).value, abs=0.01 / 1_000_000
        )

    initial = [decoder.decode(frame) for frame in raw_frames[:5]]
    assert initial[0].message_name == "DmeFastEngine"
    assert initial[0].signals["EngineSpeedRpm"] == 750.0
    assert initial[0].signals["EngineRunning"] is True
    assert initial[3].message_name == "DscVehicleMotion"
    assert initial[3].signals["VehicleSpeed"] == 0.0
    assert initial[4].message_name == "DscWheelSpeeds"

    moving_motion = next(
        frame
        for frame in raw_frames
        if frame.arbitration_id == 0x520 and frame.timestamp_microseconds == 6_000_000
    )
    moving_wheels = next(
        frame
        for frame in raw_frames
        if frame.arbitration_id == 0x521 and frame.timestamp_microseconds == 6_000_000
    )
    decoded_motion = decoder.decode(moving_motion)
    decoded_wheels = decoder.decode(moving_wheels)
    assert decoded_motion.signals["VehicleSpeed"] > 0.0
    for signal in (
        "FrontLeftWheelSpeed",
        "FrontRightWheelSpeed",
        "RearLeftWheelSpeed",
        "RearRightWheelSpeed",
    ):
        assert decoded_wheels.signals[signal] == pytest.approx(
            decoded_motion.signals["VehicleSpeed"], abs=0.01 / 1_000_000
        )


@pytest.mark.parametrize(
    "arguments,expected",
    [
        (["--scenario", "highway"], "--scenario must be one of"),
        (["--port", "70000"], "--port must be in"),
        (["--step-us", "0"], "--step-us must be positive"),
        (["--fault", "unknown"], "--fault must be one of"),
        (["--fault-at-us", "1"], "fault timing options require --fault"),
        (
            [
                "--fault",
                "charging-failure",
                "--fault-at-us",
                "10",
                "--fault-clear-at-us",
                "10",
            ],
            "--fault-clear-at-us must be greater",
        ),
        (["--fault-at-us", "-1"], "requires an unsigned integer"),
        (
            ["--fault", "charging-failure", "--fault", "map-sensor-bias"],
            "only one --fault is supported",
        ),
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


def test_gateway_help_documents_all_synthetic_fault_names() -> None:
    result = subprocess.run(
        [str(_gateway_executable()), "--help"],
        cwd=_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    for name in (
        "cooling-degradation",
        "charging-failure",
        "map-sensor-bias",
        "front-left-wheel-speed-sensor-bias",
        "--fault-at-us",
        "--fault-clear-at-us",
    ):
        assert name in result.stdout
