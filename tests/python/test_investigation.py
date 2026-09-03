import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from tuneros.api import create_app
from tuneros.can import DecodedCanFrame, RawCanFrame
from tuneros.investigation import (
    MAX_INVESTIGATION_WINDOW_MICROSECONDS,
    InvestigationCompatibilityError,
    InvestigationQueryError,
    InvestigationService,
)
from tuneros.session import (
    FRAMES_FILENAME,
    MANIFEST_FILENAME,
    SessionCatalog,
    SessionIntegrityError,
    SessionRecorder,
)
from tuneros.telemetry import SignalKey, TelemetryService

CREATED = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
BATTERY = SignalKey("DmeThermalElectrical", "BatteryVoltage")
ENGINE_RUNNING = SignalKey("DmeFastEngine", "EngineRunning")


def _record_charging_timeline(
    root: Path,
    identifier: str,
    *,
    failed_from: int | None = 1_000_000,
    recovered_from: int | None = 5_000_000,
) -> str:
    recorder = SessionRecorder(
        root,
        name="charging evidence" if failed_from is not None else "healthy baseline",
        scenario="city",
        session_id=UUID(identifier),
        created_at_utc=CREATED,
    )
    for timestamp in range(0, 10_000_001, 10_000):
        recorder.record(RawCanFrame(0x500, bytes.fromhex("b80b0f2e01"), timestamp))
        if timestamp % 100_000 == 0:
            low = (
                failed_from is not None
                and timestamp >= failed_from
                and (recovered_from is None or timestamp < recovered_from)
            )
            battery_byte = 118 if low else 142
            recorder.record(
                RawCanFrame(
                    0x502,
                    bytes.fromhex("0e06dc05e204") + bytes([battery_byte]),
                    timestamp,
                )
            )
    return recorder.complete().session_id


def _rewrite_manifest(root: Path, session_id: str, **changes: object) -> None:
    path = root / f"{session_id}.tuneros" / MANIFEST_FILENAME
    value = json.loads(path.read_text(encoding="utf-8"))
    value.update(changes)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture
def investigation_sessions(tmp_path: Path) -> tuple[InvestigationService, str, str]:
    primary = _record_charging_timeline(tmp_path, "11111111-1111-4111-8111-111111111111")
    baseline = _record_charging_timeline(
        tmp_path,
        "22222222-2222-4222-8222-222222222222",
        failed_from=None,
        recovered_from=None,
    )
    return InvestigationService(SessionCatalog(tmp_path)), primary, baseline


def test_streaming_investigation_reconstructs_pre_window_persistence_and_center_state(
    investigation_sessions: tuple[InvestigationService, str, str],
) -> None:
    service, primary, _ = investigation_sessions
    result = service.investigate(
        primary,
        center_timestamp_microseconds=4_000_000,
        before_microseconds=1_000_000,
        after_microseconds=1_000_000,
        selected_signals=(BATTERY, ENGINE_RUNNING),
        diagnostic_code="TUN-DME-003",
    )

    charging = next(
        state
        for state in result.diagnostic_states_at_center
        if state.definition.code == "TUN-DME-003"
    )
    assert charging.status == "active"
    assert charging.record is not None
    assert charging.record.first_detected_timestamp_microseconds == 1_000_000
    assert charging.record.confirmed_timestamp_microseconds == 4_000_000
    assert [event.event_type for event in result.diagnostic_events] == ["dtc_confirmed"]
    assert result.freeze_frames_at_center[0].capture_timestamp_microseconds == 4_000_000
    assert {sample.key: sample.value for sample in result.start_context} == {
        BATTERY: 11.8,
        ENGINE_RUNNING: True,
    }
    assert result.raw_frames[0].sequence > 0
    assert result.raw_frames[0].raw_frame.timestamp_microseconds == 3_000_000
    assert result.statistics.raw_frame_count == len(result.raw_frames)
    assert result.statistics.diagnostic_event_count == 1
    assert [summary.value_type for summary in result.signal_summaries] == [
        "numeric",
        "boolean",
    ]
    assert result.signal_summaries[1].mean is None
    assert result.signal_summaries[1].distinct_values == (True,)


@pytest.mark.parametrize(
    ("center", "expected"),
    [(500_000, "absent"), (2_000_000, "pending"), (4_000_000, "active"), (8_000_000, "historical")],
)
def test_diagnostic_state_is_reconstructed_at_center_not_taken_from_final_session(
    investigation_sessions: tuple[InvestigationService, str, str], center: int, expected: str
) -> None:
    service, primary, _ = investigation_sessions
    result = service.investigate(
        primary,
        center_timestamp_microseconds=center,
        before_microseconds=0,
        after_microseconds=0,
        diagnostic_code="TUN-DME-003",
    )
    state = next(
        item for item in result.diagnostic_states_at_center if item.definition.code == "TUN-DME-003"
    )
    assert ("absent" if state.status is None else state.status) == expected


def test_window_defaults_clamping_edges_and_limits(
    investigation_sessions: tuple[InvestigationService, str, str],
) -> None:
    service, primary, _ = investigation_sessions
    beginning = service.investigate(primary, center_timestamp_microseconds=0)
    ending = service.investigate(primary, center_timestamp_microseconds=10_000_000)
    zero = service.investigate(
        primary,
        center_timestamp_microseconds=5_000_000,
        before_microseconds=0,
        after_microseconds=0,
    )
    maximum = service.investigate(
        primary,
        center_timestamp_microseconds=5_000_000,
        before_microseconds=15_000_000,
        after_microseconds=15_000_000,
    )

    assert (
        beginning.window.start_timestamp_microseconds,
        beginning.window.end_timestamp_microseconds,
    ) == (
        0,
        2_000_000,
    )
    assert (
        ending.window.start_timestamp_microseconds,
        ending.window.end_timestamp_microseconds,
    ) == (
        8_000_000,
        10_000_000,
    )
    assert zero.window.duration_microseconds == 0
    assert maximum.window.duration_microseconds == 10_000_000
    with pytest.raises(InvestigationQueryError, match="within"):
        service.investigate(primary, center_timestamp_microseconds=10_000_001)
    with pytest.raises(InvestigationQueryError, match="cannot exceed"):
        service.investigate(
            primary,
            center_timestamp_microseconds=5_000_000,
            before_microseconds=MAX_INVESTIGATION_WINDOW_MICROSECONDS,
            after_microseconds=1,
        )
    with pytest.raises(InvestigationQueryError, match="non-negative"):
        service.investigate(primary, before_microseconds=-1)


def test_healthy_baseline_comparison_alignment_statistics_and_compatibility(
    investigation_sessions: tuple[InvestigationService, str, str], tmp_path: Path
) -> None:
    service, primary, baseline = investigation_sessions
    comparison = service.compare(
        primary,
        baseline,
        primary_center_timestamp_microseconds=4_000_000,
        baseline_center_timestamp_microseconds=99_000_000,
        before_microseconds=1_000_000,
        after_microseconds=1_000_000,
        selected_signals=(BATTERY, ENGINE_RUNNING),
        diagnostic_code="TUN-DME-003",
    )

    battery = comparison.signal_comparisons[0]
    assert comparison.primary.window.center_timestamp_microseconds == 4_000_000
    assert comparison.baseline.window.center_timestamp_microseconds == 10_000_000
    expected_primary_mean = (20 * 11.8 + 14.2) / 21
    assert battery.primary.mean == pytest.approx(expected_primary_mean)
    assert battery.baseline.mean == pytest.approx(14.2)
    assert battery.mean_difference == pytest.approx(expected_primary_mean - 14.2)
    assert comparison.primary_has_diagnostic_event is True
    assert comparison.baseline_has_diagnostic_event is False

    primary_manifest = service.session_catalog.reader(primary).manifest
    _rewrite_manifest(tmp_path, baseline, vehicle_profile_id="incompatible vehicle")
    with pytest.raises(InvestigationCompatibilityError, match="vehicle profile"):
        service.compare(primary, baseline)
    _rewrite_manifest(
        tmp_path,
        baseline,
        vehicle_profile_id=primary_manifest.vehicle_profile_id,
        can_network="incompatible network",
    )
    with pytest.raises(InvestigationCompatibilityError, match="CAN network"):
        service.compare(primary, baseline)


def test_api_success_export_path_safety_validation_and_active_service_isolation(
    investigation_sessions: tuple[InvestigationService, str, str], tmp_path: Path
) -> None:
    _, primary, baseline = investigation_sessions
    telemetry = TelemetryService()
    telemetry.ingest_decoded(
        DecodedCanFrame(
            0x500,
            "DmeFastEngine",
            123,
            {
                "EngineSpeedRpm": 750.0,
                "ThrottlePosition": 0.06,
                "EngineLoad": 0.18,
                "EngineRunning": True,
            },
        )
    )
    before = (
        telemetry.snapshot(),
        telemetry.diagnostic_snapshot(),
        telemetry.can_snapshot(),
        telemetry.source_status(),
    )
    app = create_app(
        telemetry,
        autostart=False,
        session_catalog=SessionCatalog(tmp_path),
    )
    query = (
        "center_us=4000000&before_us=1000000&after_us=1000000&"
        "signal=DmeThermalElectrical.BatteryVoltage&code=TUN-DME-003"
    )
    with TestClient(app) as client:
        response = client.get(f"/api/v1/sessions/{primary}/investigation?{query}")
        comparison = client.get(
            f"/api/v1/sessions/{primary}/investigation/compare?{query}&"
            f"baseline_session_id={baseline}&baseline_center_us=4000000"
        )
        first_export = client.get(f"/api/v1/sessions/{primary}/investigation/export?{query}")
        second_export = client.get(f"/api/v1/sessions/{primary}/investigation/export?{query}")
        invalid_id = client.get("/api/v1/sessions/..%2Fmanifest.json/investigation")
        absolute_id = client.get("/api/v1/sessions/C:%5CWindows/investigation")
        non_uuid = client.get("/api/v1/sessions/not-a-uuid/investigation")
        healthy = client.get(
            f"/api/v1/sessions/{baseline}/investigation?center_us=4000000&code=TUN-DME-003"
        )
        invalid_signal = client.get(
            f"/api/v1/sessions/{primary}/investigation?signal=BatteryVoltage"
        )
        invalid_window = client.get(
            f"/api/v1/sessions/{primary}/investigation?before_us=30000000&after_us=1"
        )

    assert response.status_code == 200
    assert response.json()["diagnostic_states_at_center"][2]["status"] == "active"
    assert comparison.status_code == 200
    assert comparison.json()["signal_comparisons"][0]["mean_difference"] == pytest.approx(
        (20 * 11.8 + 14.2) / 21 - 14.2
    )
    assert first_export.status_code == 200
    assert first_export.content == second_export.content
    assert first_export.headers["content-disposition"].startswith("attachment; filename=")
    assert first_export.json()["format_name"] == "tuneros.diagnostic_investigation"
    assert "artifact_path" not in first_export.text
    assert str(tmp_path) not in first_export.text
    assert invalid_id.status_code == 404
    assert absolute_id.status_code == 404
    assert non_uuid.status_code == 404
    assert healthy.status_code == 200
    assert not healthy.json()["diagnostic_events"]
    assert invalid_signal.status_code == 422
    assert invalid_window.status_code == 422
    assert before == (
        telemetry.snapshot(),
        telemetry.diagnostic_snapshot(),
        telemetry.can_snapshot(),
        telemetry.source_status(),
    )


def test_corrupt_session_is_rejected_before_investigation(
    investigation_sessions: tuple[InvestigationService, str, str], tmp_path: Path
) -> None:
    service, primary, _ = investigation_sessions
    frames = tmp_path / f"{primary}.tuneros" / FRAMES_FILENAME
    data = frames.read_bytes()
    frames.write_bytes(data[:-1])
    with pytest.raises(SessionIntegrityError, match="truncated"):
        service.investigate(primary)

    _, _, baseline = investigation_sessions
    _rewrite_manifest(tmp_path, baseline, frames_sha256="0" * 64)
    with pytest.raises(SessionIntegrityError, match="SHA-256"):
        service.investigate(baseline)
