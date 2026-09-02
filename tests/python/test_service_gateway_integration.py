import os
import queue
import subprocess
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tuneros.api import create_app
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


def _readline(stream, result: queue.Queue[str]) -> None:
    result.put(stream.readline())


def test_cpp_gateway_reaches_live_service_rest_and_websocket() -> None:
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
        service = TelemetryService(
            TelemetryServiceConfig(
                gateway_port=port,
                subscriber_queue_capacity=2_048,
            )
        )

        vehicle_speed_values: list[float] = []
        websocket_messages = 0
        saw_running = False
        with TestClient(create_app(service, autostart=False)) as client:
            with client.websocket_connect("/api/v1/ws/telemetry") as websocket:
                assert websocket.receive_json()["type"] == "initial_snapshot"
                service.start()
                while True:
                    event = websocket.receive_json()
                    if event["type"] == "service_state":
                        saw_running |= event["state"] == "running"
                        if event["state"] == "completed":
                            break
                    elif event["type"] == "telemetry_update":
                        websocket_messages += 1
                        for signal in event["signals"]:
                            if signal["key"]["signal_name"] == "VehicleSpeed":
                                vehicle_speed_values.append(signal["value"])

            status = client.get("/api/v1/status")
            snapshot = client.get("/api/v1/telemetry")
            statistics = client.get("/api/v1/statistics")

            assert status.status_code == snapshot.status_code == statistics.status_code == 200
            assert status.json()["service_state"] == "completed"
            assert status.json()["gateway_connected"] is False
            assert status.json()["last_error"] is None
            assert status.json()["latest_timestamp_microseconds"] == 6_000_000
            assert statistics.json()["total_frames"] == websocket_messages == 1_565
            assert statistics.json()["total_signal_updates"] == 5_357

            signals = {item["key"]["signal_name"]: item for item in snapshot.json()["signals"]}
            assert signals["EngineSpeedRpm"]["source_ecu"] == "TunerOsSimulatedDme"
            assert signals["VehicleSpeed"]["source_ecu"] == "TunerOsSimulatedDsc"
            assert signals["CurrentGear"] is not None
            for wheel in (
                "FrontLeftWheelSpeed",
                "FrontRightWheelSpeed",
                "RearLeftWheelSpeed",
                "RearRightWheelSpeed",
            ):
                assert signals[wheel]["source_ecu"] == "TunerOsSimulatedDsc"
            assert snapshot.json()["observation_timestamp_microseconds"] == 6_000_000

        assert saw_running
        assert len(set(vehicle_speed_values)) > 1
        assert service.state_transitions == (
            TelemetryServiceState.STOPPED,
            TelemetryServiceState.CONNECTING,
            TelemetryServiceState.RUNNING,
            TelemetryServiceState.COMPLETED,
            TelemetryServiceState.STOPPED,
        )
        return_code = process.wait(timeout=10)
        assert return_code == 0, process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
