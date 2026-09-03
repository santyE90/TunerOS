from collections.abc import Iterable

import pytest
from tuneros.can import DecodedCanFrame, RawCanFrame, TunerOsDbcDecoder
from tuneros.diagnostics import (
    DiagnosticClearError,
    DiagnosticEngine,
    DiagnosticEventType,
    DiagnosticStatus,
    UnknownDiagnosticCodeError,
    create_default_diagnostic_catalog,
)
from tuneros.session import SessionReader, SessionRecorder, replay_session
from tuneros.telemetry import SignalCatalog, TelemetryEngine


def _engines(*, event_capacity: int = 1_024) -> tuple[TelemetryEngine, DiagnosticEngine]:
    telemetry = TelemetryEngine(SignalCatalog(TunerOsDbcDecoder().database_metadata))
    diagnostics = DiagnosticEngine(
        create_default_diagnostic_catalog(telemetry.catalog), event_capacity
    )
    return telemetry, diagnostics


def _fast(timestamp: int, *, running: bool = True) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x500,
        "DmeFastEngine",
        timestamp,
        {
            "EngineSpeedRpm": 750.0 if running else 0.0,
            "ThrottlePosition": 0.06 if running else 0.0,
            "EngineLoad": 0.18 if running else 0.0,
            "EngineRunning": running,
        },
    )


def _air(timestamp: int, *, pressure: float = 45.0) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x501,
        "DmeAirLoad",
        timestamp,
        {
            "ManifoldPressureAbsolute": pressure,
            "AcceleratorPedalPosition": 0.0,
            "RequestedScenarioLoad": 0.18,
        },
    )


def _thermal(
    timestamp: int,
    *,
    coolant: float = 90.0,
    oil: float = 100.0,
    battery: float = 14.2,
) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x502,
        "DmeThermalElectrical",
        timestamp,
        {
            "CoolantTemperature": coolant,
            "OilTemperature": oil,
            "IntakeAirTemperature": 30.0,
            "BatteryVoltage": battery,
        },
    )


def _motion(timestamp: int, *, speed: float = 10.0) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x520,
        "DscVehicleMotion",
        timestamp,
        {"VehicleSpeed": speed, "CurrentGear": 2},
    )


def _wheels(
    timestamp: int, *, speeds: tuple[float, float, float, float] = (10.0, 10.0, 10.0, 10.0)
) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x521,
        "DscWheelSpeeds",
        timestamp,
        dict(
            zip(
                (
                    "FrontLeftWheelSpeed",
                    "FrontRightWheelSpeed",
                    "RearLeftWheelSpeed",
                    "RearRightWheelSpeed",
                ),
                speeds,
                strict=True,
            )
        ),
    )


def _ingest(
    telemetry: TelemetryEngine,
    diagnostics: DiagnosticEngine,
    frames: Iterable[DecodedCanFrame],
) -> None:
    for frame in frames:
        telemetry.ingest(frame)
        diagnostics.ingest(telemetry.snapshot())


def _thermal_range(
    start: int,
    stop: int,
    *,
    coolant: float = 90.0,
    oil: float = 100.0,
    battery: float = 14.2,
) -> tuple[DecodedCanFrame, ...]:
    return tuple(
        _thermal(timestamp, coolant=coolant, oil=oil, battery=battery)
        for timestamp in range(start, stop + 1, 100_000)
    )


def test_empty_snapshot_catalog_and_capacity_validation() -> None:
    telemetry, diagnostics = _engines()

    assert diagnostics.catalog.rules[0].definition.code == "TUN-DME-001"
    assert len(diagnostics.catalog.rules) == 5
    assert diagnostics.ingest(telemetry.snapshot()) == ()
    assert diagnostics.dtcs() == ()
    assert diagnostics.events() == ()
    assert diagnostics.snapshot().observation_timestamp_microseconds is None
    assert diagnostics.snapshot().latest_telemetry_frame_sequence is None
    assert diagnostics.snapshot().latest_event_sequence is None
    assert diagnostics.snapshot().active_count == 0
    with pytest.raises(ValueError, match="positive"):
        DiagnosticEngine(diagnostics.catalog, 0)
    with pytest.raises(TypeError, match="integer"):
        DiagnosticEngine(diagnostics.catalog, True)


@pytest.mark.parametrize(
    ("code", "frames", "frames_at_confirmation"),
    [
        ("TUN-DME-001", _thermal_range(0, 5_000_000, coolant=116.0), 1),
        ("TUN-DME-002", _thermal_range(0, 5_000_000, oil=136.0), 1),
        (
            "TUN-DME-003",
            tuple(
                frame
                for timestamp in range(0, 3_000_001, 100_000)
                for frame in (_fast(timestamp), _thermal(timestamp, battery=12.0))
            ),
            2,
        ),
        (
            "TUN-DME-004",
            tuple(
                frame
                for timestamp in range(0, 2_000_001, 20_000)
                for frame in (_fast(timestamp), _air(timestamp, pressure=260.0))
            ),
            2,
        ),
        (
            "TUN-DSC-001",
            tuple(
                frame
                for timestamp in range(0, 1_000_001, 20_000)
                for frame in (
                    _motion(timestamp),
                    _wheels(timestamp, speeds=(15.0, 10.0, 10.0, 10.0)),
                )
            ),
            2,
        ),
    ],
)
def test_each_catalog_rule_confirms_from_fresh_decoded_telemetry(
    code: str, frames: tuple[DecodedCanFrame, ...], frames_at_confirmation: int
) -> None:
    telemetry, diagnostics = _engines()
    _ingest(telemetry, diagnostics, frames[:-frames_at_confirmation])
    pending = diagnostics.dtc(code)
    assert pending is not None and pending.status is DiagnosticStatus.PENDING

    _ingest(telemetry, diagnostics, frames[-frames_at_confirmation:])

    dtc = diagnostics.dtc(code)
    assert dtc is not None
    assert dtc.status is DiagnosticStatus.ACTIVE
    assert dtc.occurrence_count == 1
    assert diagnostics.freeze_frame(code) is not None


def test_coolant_exact_confirmation_recovery_hysteresis_recurrence_and_clear() -> None:
    telemetry, diagnostics = _engines()
    _ingest(telemetry, diagnostics, (_thermal(0, coolant=116.0),))
    pending = diagnostics.dtc("TUN-DME-001")
    assert pending is not None and pending.status is DiagnosticStatus.PENDING

    _ingest(telemetry, diagnostics, (_thermal(4_999_999, coolant=116.0),))
    assert diagnostics.dtc("TUN-DME-001").status is DiagnosticStatus.PENDING  # type: ignore[union-attr]
    _ingest(telemetry, diagnostics, (_thermal(5_000_000, coolant=116.0),))
    active = diagnostics.dtc("TUN-DME-001")
    assert active is not None and active.status is DiagnosticStatus.ACTIVE
    assert active.confirmed_timestamp_microseconds == 5_000_000
    original_freeze = diagnostics.freeze_frame("TUN-DME-001")

    # Between activation and recovery thresholds remains latched active.
    _ingest(telemetry, diagnostics, (_thermal(8_000_000, coolant=112.0),))
    assert diagnostics.dtc("TUN-DME-001").status is DiagnosticStatus.ACTIVE  # type: ignore[union-attr]
    _ingest(telemetry, diagnostics, (_thermal(8_000_001, coolant=109.0),))
    _ingest(telemetry, diagnostics, (_thermal(11_000_000, coolant=109.0),))
    assert diagnostics.dtc("TUN-DME-001").status is DiagnosticStatus.ACTIVE  # type: ignore[union-attr]
    _ingest(telemetry, diagnostics, (_thermal(11_000_001, coolant=109.0),))
    historical = diagnostics.dtc("TUN-DME-001")
    assert historical is not None and historical.status is DiagnosticStatus.HISTORICAL

    _ingest(telemetry, diagnostics, (_thermal(12_000_000, coolant=116.0),))
    assert diagnostics.dtc("TUN-DME-001").status is DiagnosticStatus.PENDING  # type: ignore[union-attr]
    _ingest(telemetry, diagnostics, (_thermal(17_000_000, coolant=116.0),))
    recurrent = diagnostics.dtc("TUN-DME-001")
    assert recurrent is not None and recurrent.status is DiagnosticStatus.ACTIVE
    assert recurrent.first_detected_timestamp_microseconds == 0
    assert recurrent.confirmed_timestamp_microseconds == 17_000_000
    assert recurrent.occurrence_count == 2
    assert diagnostics.freeze_frame("TUN-DME-001") == original_freeze

    _ingest(telemetry, diagnostics, (_thermal(18_000_000, coolant=100.0),))
    _ingest(telemetry, diagnostics, (_thermal(20_999_999, coolant=100.0),))
    with pytest.raises(DiagnosticClearError, match="active"):
        diagnostics.clear("TUN-DME-001")
    _ingest(telemetry, diagnostics, (_thermal(21_000_000, coolant=100.0),))
    cleared = diagnostics.clear("TUN-DME-001")
    assert cleared.status is DiagnosticStatus.CLEARED
    assert diagnostics.clear("TUN-DME-001") == cleared
    assert diagnostics.freeze_frame("TUN-DME-001") == original_freeze


def test_pending_clears_without_historical_record() -> None:
    telemetry, diagnostics = _engines()
    _ingest(
        telemetry,
        diagnostics,
        (_thermal(0, coolant=116.0), _thermal(1_000_000, coolant=90.0)),
    )

    assert diagnostics.dtc("TUN-DME-001") is None
    assert [event.event_type for event in diagnostics.events()] == [
        DiagnosticEventType.CONDITION_DETECTED,
        DiagnosticEventType.CONDITION_CLEARED,
    ]


def test_engine_off_low_voltage_is_normal_and_missing_signals_are_unavailable() -> None:
    telemetry, diagnostics = _engines()
    _ingest(telemetry, diagnostics, (_thermal(0, battery=12.0),))
    assert diagnostics.dtcs() == ()
    _ingest(telemetry, diagnostics, (_fast(0, running=False),))
    assert diagnostics.dtcs() == ()


def test_stale_inputs_neither_confirm_pending_nor_recover_active() -> None:
    telemetry, diagnostics = _engines()
    _ingest(telemetry, diagnostics, (_thermal(0, coolant=116.0),))
    _ingest(telemetry, diagnostics, (_fast(300_000), _thermal(5_000_000, coolant=116.0)))
    assert diagnostics.dtc("TUN-DME-001").status is DiagnosticStatus.PENDING  # type: ignore[union-attr]

    diagnostics.reset()
    telemetry.reset()
    _ingest(telemetry, diagnostics, _thermal_range(0, 5_000_000, coolant=116.0))
    assert diagnostics.dtc("TUN-DME-001").status is DiagnosticStatus.ACTIVE  # type: ignore[union-attr]
    _ingest(telemetry, diagnostics, (_thermal(5_100_000, coolant=90.0), _fast(5_400_001)))
    assert diagnostics.dtc("TUN-DME-001").status is DiagnosticStatus.ACTIVE  # type: ignore[union-attr]


def test_same_timestamp_catalog_event_order_and_no_duplicate_transitions() -> None:
    telemetry, diagnostics = _engines()
    frame = _thermal(0, coolant=116.0, oil=136.0)
    _ingest(telemetry, diagnostics, (frame, frame))

    assert [(event.sequence, event.code) for event in diagnostics.events()] == [
        (0, "TUN-DME-001"),
        (1, "TUN-DME-002"),
    ]


def test_freeze_frame_is_all_observed_immutable_telemetry() -> None:
    telemetry, diagnostics = _engines()
    _ingest(telemetry, diagnostics, (_fast(0),))
    _ingest(telemetry, diagnostics, _thermal_range(0, 5_000_000, coolant=116.0))
    frozen = diagnostics.freeze_frame("TUN-DME-001")
    assert frozen is not None
    assert frozen.capture_timestamp_microseconds == 5_000_000
    assert len(frozen.signals) == 8
    assert {signal.source_ecu for signal in frozen.signals} == {"TunerOsSimulatedDme"}

    _ingest(telemetry, diagnostics, (_thermal(5_100_000, coolant=200.0),))
    assert diagnostics.freeze_frame("TUN-DME-001") == frozen


def test_returned_snapshot_is_an_immutable_point_in_time() -> None:
    telemetry, diagnostics = _engines()
    _ingest(telemetry, diagnostics, _thermal_range(0, 5_000_000, coolant=116.0))
    active_snapshot = diagnostics.snapshot()

    _ingest(telemetry, diagnostics, (_thermal(6_000_000, coolant=100.0),))
    _ingest(telemetry, diagnostics, (_thermal(9_000_000, coolant=100.0),))

    assert active_snapshot.active_count == 1
    assert active_snapshot.historical_count == 0
    assert active_snapshot.dtcs[0].status is DiagnosticStatus.ACTIVE
    assert diagnostics.snapshot().dtcs[0].status is DiagnosticStatus.HISTORICAL


def test_reset_reproduces_snapshot_events_and_freeze_frame_exactly() -> None:
    telemetry, diagnostics = _engines()
    sequence = _thermal_range(0, 5_000_000, coolant=116.0)
    _ingest(telemetry, diagnostics, sequence)
    first = diagnostics.snapshot(), diagnostics.events(), diagnostics.freeze_frame("TUN-DME-001")

    telemetry.reset()
    diagnostics.reset()
    _ingest(telemetry, diagnostics, sequence)
    second = diagnostics.snapshot(), diagnostics.events(), diagnostics.freeze_frame("TUN-DME-001")
    assert second == first


def test_event_history_is_bounded_without_reusing_sequences() -> None:
    telemetry, diagnostics = _engines(event_capacity=2)
    _ingest(
        telemetry,
        diagnostics,
        (
            _thermal(0, coolant=116.0),
            _thermal(1, coolant=90.0),
            _thermal(2, coolant=116.0),
            _thermal(3, coolant=90.0),
        ),
    )

    assert [event.sequence for event in diagnostics.events()] == [2, 3]
    snapshot = diagnostics.snapshot()
    assert snapshot.retained_event_count == 2
    assert snapshot.total_event_count == 4
    assert snapshot.latest_event_sequence == 3
    assert diagnostics.events(limit=1)[0].sequence == 3
    with pytest.raises(ValueError, match="positive"):
        diagnostics.events(limit=0)
    with pytest.raises(UnknownDiagnosticCodeError, match="unknown"):
        diagnostics.dtc("TUN-NOPE-001")


def test_triggering_raw_session_replay_rebuilds_identical_diagnostics(tmp_path) -> None:
    raw_frames = tuple(
        RawCanFrame(0x502, bytes.fromhex("7008D00714058E"), timestamp)
        for timestamp in range(0, 5_000_001, 100_000)
    )
    recorder = SessionRecorder(tmp_path, name="synthetic coolant diagnostic")
    telemetry, diagnostics = _engines()
    decoder = TunerOsDbcDecoder()
    for raw_frame in raw_frames:
        recorder.record(raw_frame)
        telemetry.ingest(decoder.decode(raw_frame))
        diagnostics.ingest(telemetry.snapshot())
    recorder.complete()

    replay = replay_session(SessionReader(recorder.artifact_path))
    assert replay.diagnostics.snapshot() == diagnostics.snapshot()
    assert replay.diagnostics.events() == diagnostics.events()
    assert replay.diagnostics.freeze_frame("TUN-DME-001") == diagnostics.freeze_frame("TUN-DME-001")
    assert replay.diagnostics.dtc("TUN-DME-001").status is DiagnosticStatus.ACTIVE  # type: ignore[union-attr]
