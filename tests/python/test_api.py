from fastapi.testclient import TestClient
from tuneros.api import create_app
from tuneros.can import (
    CanDatabaseMetadata,
    CanExplorer,
    CanMessageMetadata,
    CanSignalMetadata,
    DecodedCanFrame,
    GatewayConnectionError,
    RawCanFrame,
)
from tuneros.session import SessionCatalog, SessionRecorder
from tuneros.telemetry import (
    SignalCatalog,
    TelemetryEngine,
    TelemetryService,
    TelemetryServiceConfig,
    TelemetryServiceState,
)


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


def _motion(timestamp: int, speed: float = 0.0, gear: int = 0) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x520,
        "DscVehicleMotion",
        timestamp,
        {"VehicleSpeed": speed, "CurrentGear": gear},
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


def _wheels(timestamp: int, speed: float = 0.0) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x521,
        "DscWheelSpeeds",
        timestamp,
        {
            "FrontLeftWheelSpeed": speed,
            "FrontRightWheelSpeed": speed,
            "RearLeftWheelSpeed": speed,
            "RearRightWheelSpeed": speed,
        },
    )


def test_empty_status_snapshot_catalog_statistics_and_openapi() -> None:
    service = TelemetryService()
    with TestClient(create_app(service, autostart=False)) as client:
        status = client.get("/api/v1/status")
        snapshot = client.get("/api/v1/telemetry")
        catalog = client.get("/api/v1/catalog")
        statistics = client.get("/api/v1/statistics")
        openapi = client.get("/openapi.json")
        can_frames = client.get("/api/v1/can/frames")
        can_statistics = client.get("/api/v1/can/statistics")
        can_messages = client.get("/api/v1/can/messages")
        diagnostics = client.get("/api/v1/diagnostics")
        dtcs = client.get("/api/v1/diagnostics/dtcs")
        diagnostic_events = client.get("/api/v1/diagnostics/events")

    assert status.status_code == 200
    assert status.json() == {
        "service_state": "stopped",
        "gateway_connected": False,
        "last_error": None,
        "latest_timestamp_microseconds": None,
        "total_frames": 0,
        "total_signal_updates": 0,
    }
    assert snapshot.json()["signals"] == []
    assert snapshot.json()["observation_timestamp_microseconds"] is None
    assert len(catalog.json()) == 17
    assert statistics.json()["frames_by_message"] == []
    assert openapi.status_code == 200
    assert can_frames.json() == []
    assert can_statistics.json()["total_frame_count"] == 0
    assert can_statistics.json()["source"]["mode"] == "live"
    assert can_messages.json() == []
    assert diagnostics.json()["observation_timestamp_microseconds"] is None
    assert diagnostics.json()["active_count"] == 0
    assert diagnostics.json()["source"]["mode"] == "live"
    assert dtcs.json() == []
    assert diagnostic_events.json() == []


def test_diagnostic_rest_lifecycle_freeze_frame_filter_limit_and_clear() -> None:
    service = TelemetryService()
    service.ingest_decoded(_fast(0))
    service.ingest_decoded(_thermal(0, 116.0))

    with TestClient(create_app(service, autostart=False)) as client:
        pending = client.get("/api/v1/diagnostics/dtcs/TUN-DME-001")
        pending_filter = client.get("/api/v1/diagnostics/dtcs?status=pending")
        missing_freeze = client.get("/api/v1/diagnostics/dtcs/TUN-DME-001/freeze-frame")
        unknown = client.get("/api/v1/diagnostics/dtcs/TUN-NOPE-001")

    assert pending.json()["status"] == "pending"
    assert pending.json()["definition"]["severity"] == "critical"
    assert pending.json()["definition"]["source_system"] == "DME"
    assert len(pending_filter.json()) == 1
    assert missing_freeze.status_code == 404
    assert unknown.status_code == 404

    for timestamp in range(100_000, 5_000_001, 100_000):
        service.ingest_decoded(_thermal(timestamp, 116.0))

    with TestClient(create_app(service, autostart=False)) as client:
        active = client.get("/api/v1/diagnostics/dtcs/TUN-DME-001")
        freeze = client.get("/api/v1/diagnostics/dtcs/TUN-DME-001/freeze-frame")
        active_clear = client.post("/api/v1/diagnostics/dtcs/TUN-DME-001/clear")
        events = client.get("/api/v1/diagnostics/events?limit=1")
        invalid_limit = client.get("/api/v1/diagnostics/events?limit=0")

    assert active.json()["status"] == "active"
    assert active.json()["occurrence_count"] == 1
    assert active_clear.status_code == 409
    assert freeze.json()["capture_timestamp_microseconds"] == 5_000_000
    assert freeze.json()["telemetry_frame_sequence"] == 51
    assert len(freeze.json()["signals"]) == 8
    assert freeze.json()["signals"][0]["key"] == {
        "message_name": "DmeFastEngine",
        "signal_name": "EngineLoad",
    }
    assert freeze.json()["signals"][0]["arbitration_id_hex"] == "0x500"
    assert events.json()[0]["event_type"] == "dtc_confirmed"
    assert invalid_limit.status_code == 422

    for timestamp in range(5_100_000, 8_100_001, 100_000):
        service.ingest_decoded(_thermal(timestamp, 90.0))

    with TestClient(create_app(service, autostart=False)) as client:
        historical = client.get("/api/v1/diagnostics/dtcs?status=historical")
        cleared = client.post("/api/v1/diagnostics/dtcs/TUN-DME-001/clear")
        idempotent = client.post("/api/v1/diagnostics/dtcs/TUN-DME-001/clear")
        summary = client.get("/api/v1/diagnostics")
        all_events = client.get("/api/v1/diagnostics/events")

    assert historical.json()[0]["status"] == "historical"
    assert cleared.json()["status"] == "cleared"
    assert idempotent.json() == cleared.json()
    assert summary.json()["cleared_count"] == 1
    assert summary.json()["latest_event_sequence"] == 3
    assert [item["event_type"] for item in all_events.json()] == [
        "condition_detected",
        "dtc_confirmed",
        "dtc_recovered",
        "dtc_cleared",
    ]


def test_can_rest_frames_filters_detail_statistics_unknown_and_decode_error() -> None:
    explorer = CanExplorer(capacity=4)
    explorer.ingest(RawCanFrame(0x500, bytes.fromhex("7017804001"), 0))
    explorer.ingest(RawCanFrame(0x123, bytes.fromhex("AA00"), 10_000))
    explorer.ingest(RawCanFrame(0x500, b"\x01", 20_000))
    explorer.ingest(RawCanFrame(0x520, bytes.fromhex("000000"), 20_000))
    explorer.ingest(RawCanFrame(0x521, bytes.fromhex("0000000000000000"), 20_000))
    service = TelemetryService(
        config=TelemetryServiceConfig(can_explorer_capacity=4), explorer=explorer
    )

    with TestClient(create_app(service, autostart=False)) as client:
        frames = client.get("/api/v1/can/frames?limit=4")
        by_id = client.get("/api/v1/can/frames?arbitration_id=1280")
        by_message = client.get("/api/v1/can/frames?message_name=DscVehicleMotion")
        by_source = client.get("/api/v1/can/frames?source_ecu=TunerOsSimulatedDsc")
        detail = client.get("/api/v1/can/frames/2")
        evicted = client.get("/api/v1/can/frames/0")
        messages = client.get("/api/v1/can/messages")
        invalid_limits = (
            client.get("/api/v1/can/frames?limit=0"),
            client.get("/api/v1/can/frames?limit=1001"),
        )

    assert frames.status_code == 200
    assert [item["sequence"] for item in frames.json()] == [1, 2, 3, 4]
    unknown = frames.json()[0]
    assert unknown["arbitration_id_hex"] == "0x123"
    assert unknown["payload"] == [170, 0]
    assert unknown["payload_hex"] == "AA 00"
    assert unknown["message_name"] is None
    assert unknown["decode_status"] == "unknown"
    malformed = detail.json()
    assert malformed["decode_status"] == "error"
    assert malformed["message_name"] == "DmeFastEngine"
    assert "requires DLC 5" in malformed["decode_error"]
    assert [item["sequence"] for item in by_id.json()] == [2]
    assert [item["sequence"] for item in by_message.json()] == [3]
    assert [item["sequence"] for item in by_source.json()] == [3, 4]
    assert evicted.status_code == 404
    assert [item["arbitration_id"] for item in messages.json()] == [0x123, 0x500, 0x520, 0x521]
    assert all(response.status_code == 422 for response in invalid_limits)


def test_latest_signal_canonical_lookup_types_provenance_units_and_freshness() -> None:
    service = TelemetryService()
    service.ingest_decoded(_fast(0))
    service.ingest_decoded(_motion(30_001, 1.25, 1))

    with TestClient(create_app(service, autostart=False)) as client:
        rpm = client.get("/api/v1/signals/EngineSpeedRpm")
        canonical = client.get("/api/v1/messages/DmeFastEngine/signals/EngineRunning")
        snapshot = client.get("/api/v1/telemetry")

    assert rpm.status_code == 200
    assert rpm.json()["sample"]["value"] == 750.0
    assert type(rpm.json()["sample"]["value"]) is float
    assert rpm.json()["sample"]["source_ecu"] == "TunerOsSimulatedDme"
    assert rpm.json()["sample"]["unit"] == "rpm"
    assert rpm.json()["freshness"] == "stale"
    assert canonical.status_code == 200
    assert canonical.json()["sample"]["value"] is True
    current_gear = next(
        signal
        for signal in snapshot.json()["signals"]
        if signal["key"]["signal_name"] == "CurrentGear"
    )
    assert type(current_gear["value"]) is int


def test_never_seen_unknown_and_ambiguous_signal_responses() -> None:
    service = TelemetryService()
    with TestClient(create_app(service, autostart=False)) as client:
        never_seen = client.get("/api/v1/signals/CoolantTemperature")
        unknown = client.get("/api/v1/signals/DoesNotExist")
        unknown_canonical = client.get("/api/v1/messages/Unknown/signals/Speed")

    assert never_seen.status_code == 200
    assert never_seen.json()["sample"] is None
    assert never_seen.json()["freshness"] is None
    assert unknown.status_code == 404
    assert unknown_canonical.status_code == 404

    metadata = CanDatabaseMetadata(
        (
            CanMessageMetadata(1, "First", "EcuA", 10_000, (CanSignalMetadata("Speed", "m/s"),)),
            CanMessageMetadata(2, "Second", "EcuB", 10_000, (CanSignalMetadata("Speed", "m/s"),)),
        )
    )
    ambiguous_service = TelemetryService(engine=TelemetryEngine(SignalCatalog(metadata)))
    with TestClient(create_app(ambiguous_service, autostart=False)) as client:
        ambiguous = client.get("/api/v1/signals/Speed")
        canonical = client.get("/api/v1/messages/Second/signals/Speed")
    assert ambiguous.status_code == 409
    assert canonical.status_code == 200


def test_history_limit_returns_recent_samples_oldest_to_newest_and_validates() -> None:
    service = TelemetryService()
    for sequence in range(5):
        service.ingest_decoded(_fast(sequence * 10_000, 700.0 + sequence))

    with TestClient(create_app(service, autostart=False)) as client:
        history = client.get("/api/v1/signals/EngineSpeedRpm/history?limit=3")
        zero = client.get("/api/v1/signals/EngineSpeedRpm/history?limit=0")
        excessive = client.get("/api/v1/signals/EngineSpeedRpm/history?limit=257")

    assert history.status_code == 200
    assert [sample["value"] for sample in history.json()["samples"]] == [702.0, 703.0, 704.0]
    assert zero.status_code == 422
    assert excessive.status_code == 422


def test_statistics_use_explicit_json_safe_message_counts() -> None:
    service = TelemetryService()
    service.ingest_decoded(_fast(0))
    service.ingest_decoded(_motion(0))

    with TestClient(create_app(service, autostart=False)) as client:
        response = client.get("/api/v1/statistics")

    assert response.json()["frames_by_message"] == [
        {
            "arbitration_id": 1280,
            "arbitration_id_hex": "0x500",
            "message_name": "DmeFastEngine",
            "frames": 1,
        },
        {
            "arbitration_id": 1312,
            "arbitration_id_hex": "0x520",
            "message_name": "DscVehicleMotion",
            "frames": 1,
        },
    ]


def test_websocket_initial_snapshot_and_atomic_ordered_dme_dsc_deltas() -> None:
    service = TelemetryService()
    with (
        TestClient(create_app(service, autostart=False)) as client,
        client.websocket_connect("/api/v1/ws/telemetry") as websocket,
    ):
        initial = websocket.receive_json()
        assert initial["type"] == "initial_snapshot"
        assert initial["snapshot"]["signals"] == []

        service.ingest_decoded(_fast(100))
        service.ingest_decoded(_motion(100, 2.0, 1))
        service.ingest_decoded(_wheels(100, 2.0))
        dme = websocket.receive_json()
        dsc = websocket.receive_json()
        wheels = websocket.receive_json()

        assert dme["type"] == dsc["type"] == "telemetry_update"
        assert dme["frame_sequence"] == 0
        assert dsc["frame_sequence"] == 1
        assert dme["timestamp_microseconds"] == dsc["timestamp_microseconds"] == 100
        assert dme["message_name"] == "DmeFastEngine"
        assert len(dme["signals"]) == 4
        assert dsc["message_name"] == "DscVehicleMotion"
        assert len(dsc["signals"]) == 2
        assert wheels["frame_sequence"] == 2
        assert wheels["message_name"] == "DscWheelSpeeds"
        assert len(wheels["signals"]) == 4

    assert service.subscriber_count == 0


def test_websocket_multiple_clients_receive_same_frame_event() -> None:
    service = TelemetryService()
    with (
        TestClient(create_app(service, autostart=False)) as client,
        client.websocket_connect("/api/v1/ws/telemetry") as first,
        client.websocket_connect("/api/v1/ws/telemetry") as second,
    ):
        first.receive_json()
        second.receive_json()
        service.ingest_decoded(_fast(0))
        assert first.receive_json() == second.receive_json()


def test_cors_is_narrowly_configured_for_local_frontend() -> None:
    service = TelemetryService()
    with TestClient(create_app(service, autostart=False)) as client:
        allowed = client.options(
            "/api/v1/status",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = client.options(
            "/api/v1/status",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in denied.headers


def test_lifespan_starts_service_and_websocket_reports_failure_then_closes() -> None:
    def fail(**_: object):
        raise GatewayConnectionError("gateway unavailable for test")

    service = TelemetryService(gateway_connector=fail)
    with TestClient(create_app(service)) as client:
        assert service.wait_for_state(TelemetryServiceState.FAILED)
        assert client.get("/api/v1/status").json()["service_state"] == "failed"
        with client.websocket_connect("/api/v1/ws/telemetry") as websocket:
            assert websocket.receive_json()["type"] == "initial_snapshot"
            failure = websocket.receive_json()
            assert failure == {
                "type": "service_state",
                "state": "failed",
                "error": "gateway unavailable for test",
            }

    assert service.state is TelemetryServiceState.STOPPED


def test_connected_websocket_receives_gateway_failure_event() -> None:
    def fail(**_: object):
        raise GatewayConnectionError("connected client failure")

    service = TelemetryService(gateway_connector=fail)
    with (
        TestClient(create_app(service, autostart=False)) as client,
        client.websocket_connect("/api/v1/ws/telemetry") as websocket,
    ):
        assert websocket.receive_json()["type"] == "initial_snapshot"
        service.start()
        assert websocket.receive_json()["state"] == "connecting"
        failure = websocket.receive_json()
        assert failure["type"] == "service_state"
        assert failure["state"] == "failed"
        assert failure["error"] == "connected client failure"


def test_session_list_detail_source_and_replay_api(tmp_path) -> None:
    recorder = SessionRecorder(tmp_path, name="CITY baseline", scenario="city")
    recorder.record(RawCanFrame(0x500, bytes.fromhex("b80b0f2e01"), 0))
    recorder.record(RawCanFrame(0x520, bytes.fromhex("640001"), 20_000))
    manifest = recorder.complete()
    service = TelemetryService()
    app = create_app(
        service,
        autostart=False,
        session_catalog=SessionCatalog(tmp_path),
    )

    with TestClient(app) as client:
        source = client.get("/api/v1/source")
        sessions = client.get("/api/v1/sessions")
        detail = client.get(f"/api/v1/sessions/{manifest.session_id}")
        missing = client.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000")
        traversal = client.get("/api/v1/sessions/..%2Fmanifest.json")
        replay = client.post(f"/api/v1/sessions/{manifest.session_id}/replay")

        assert source.json() == {
            "mode": "live",
            "session_id": None,
            "session_name": None,
            "recording": False,
            "recorded_frame_count": 0,
        }
        assert sessions.status_code == 200
        assert sessions.json() == [
            {
                "session_id": manifest.session_id,
                "name": "CITY baseline",
                "created_at_utc": manifest.created_at_utc,
                "scenario": "city",
                "status": "complete",
                "frame_count": 2,
                "duration_microseconds": 20_000,
                "dbc_compatible": True,
            }
        ]
        assert detail.status_code == 200
        assert detail.json()["frames_sha256"] == manifest.frames_sha256
        assert detail.json()["first_timestamp_microseconds"] == 0
        assert all("path" not in key for key in detail.json())
        assert str(tmp_path) not in detail.text
        assert missing.status_code == 404
        assert traversal.status_code == 404
        assert replay.status_code == 202
        assert replay.json()["source_mode"] == "replay"

        with client.websocket_connect("/api/v1/ws/telemetry") as websocket:
            assert websocket.receive_json()["snapshot"]["signals"] == []
            first = websocket.receive_json()
            second = websocket.receive_json()
            completed = websocket.receive_json()
            assert first["frame_sequence"] == 0
            assert second["frame_sequence"] == 1
            assert completed["state"] == "completed"

        replay_source = client.get("/api/v1/source").json()
        assert replay_source["mode"] == "replay"
        assert replay_source["session_id"] == manifest.session_id
        assert replay_source["session_name"] == "CITY baseline"


def test_session_api_empty_and_incomplete_policy(tmp_path) -> None:
    incomplete = SessionRecorder(tmp_path)
    incomplete.abort("test failure")
    service = TelemetryService()
    with TestClient(
        create_app(service, autostart=False, session_catalog=SessionCatalog(tmp_path))
    ) as client:
        assert client.get("/api/v1/sessions").json() == []
        assert client.get(f"/api/v1/sessions/{incomplete.manifest.session_id}").status_code == 404
        assert (
            client.post(f"/api/v1/sessions/{incomplete.manifest.session_id}/replay").status_code
            == 404
        )


def test_can_websocket_replay_snapshot_raw_order_and_completion(tmp_path) -> None:
    recorder = SessionRecorder(tmp_path, name="one-second opening")
    raw_frames = (
        RawCanFrame(0x500, bytes.fromhex("480d0f2e01"), 0),
        RawCanFrame(0x501, bytes.fromhex("9501001a"), 0),
        RawCanFrame(0x502, bytes.fromhex("b004b004b0047e"), 0),
        RawCanFrame(0x520, bytes.fromhex("000000"), 0),
        RawCanFrame(0x521, bytes.fromhex("0000000000000000"), 0),
    )
    for frame in raw_frames:
        recorder.record(frame)
    manifest = recorder.complete()
    service = TelemetryService()

    with TestClient(
        create_app(service, autostart=False, session_catalog=SessionCatalog(tmp_path))
    ) as client:
        assert client.post(f"/api/v1/sessions/{manifest.session_id}/replay").status_code == 202
        with client.websocket_connect("/api/v1/ws/can") as websocket:
            initial = websocket.receive_json()
            assert initial["type"] == "initial_can_snapshot"
            assert initial["frames"] == []
            assert initial["statistics"]["source"]["mode"] == "replay"
            events = [websocket.receive_json() for _ in raw_frames]
            terminal = websocket.receive_json()

    assert [event["type"] for event in events] == ["can_frame"] * 5
    assert [event["frame"]["sequence"] for event in events] == [0, 1, 2, 3, 4]
    assert [event["frame"]["arbitration_id"] for event in events] == [
        0x500,
        0x501,
        0x502,
        0x520,
        0x521,
    ]
    assert all(event["frame"]["timestamp_microseconds"] == 0 for event in events)
    assert terminal["type"] == "can_source_state"
    assert terminal["state"] == "completed"


def test_can_websocket_preserves_unknown_frame_before_telemetry_failure(tmp_path) -> None:
    raw = RawCanFrame(0x123, bytes.fromhex("AABB"), 0)
    recorder = SessionRecorder(tmp_path)
    recorder.record(raw)
    manifest = recorder.complete()
    service = TelemetryService()

    with TestClient(
        create_app(service, autostart=False, session_catalog=SessionCatalog(tmp_path))
    ) as client:
        client.post(f"/api/v1/sessions/{manifest.session_id}/replay")
        with client.websocket_connect("/api/v1/ws/can") as websocket:
            assert websocket.receive_json()["type"] == "initial_can_snapshot"
            observed = websocket.receive_json()
            failed = websocket.receive_json()

    assert observed["frame"]["arbitration_id"] == 0x123
    assert observed["frame"]["payload_hex"] == "AA BB"
    assert observed["frame"]["decode_status"] == "unknown"
    assert failed["type"] == "can_source_state"
    assert failed["state"] == "failed"
    assert "not defined" in failed["error"]
