from dataclasses import FrozenInstanceError

import pytest
from tuneros.can import DecodedCanFrame, TunerOsDbcDecoder
from tuneros.telemetry import (
    OutOfOrderTelemetryError,
    SignalCatalog,
    SignalFreshness,
    SignalKey,
    TelemetryEngine,
    TelemetrySchemaError,
)


@pytest.fixture
def catalog() -> SignalCatalog:
    return SignalCatalog(TunerOsDbcDecoder().database_metadata)


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


def _thermal(timestamp: int, coolant: float = 55.0) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x502,
        "DmeThermalElectrical",
        timestamp,
        {
            "CoolantTemperature": coolant,
            "OilTemperature": 50.0,
            "IntakeAirTemperature": 25.0,
            "BatteryVoltage": 14.2,
        },
    )


def _motion(timestamp: int, speed: float = 0.0, gear: int = 0) -> DecodedCanFrame:
    return DecodedCanFrame(
        0x520,
        "DscVehicleMotion",
        timestamp,
        {"VehicleSpeed": speed, "CurrentGear": gear},
    )


def test_empty_engine_and_history_capacity_validation(catalog: SignalCatalog) -> None:
    engine = TelemetryEngine(catalog)
    rpm_key = SignalKey("DmeFastEngine", "EngineSpeedRpm")

    assert engine.history_capacity == 256
    assert engine.latest(rpm_key) is None
    assert engine.latest_all() == {}
    assert engine.history(rpm_key) == ()
    assert engine.freshness(rpm_key) is None
    snapshot = engine.snapshot()
    assert snapshot.observation_timestamp_microseconds is None
    assert snapshot.last_frame_sequence is None
    assert snapshot.samples == {}
    assert snapshot.statistics.total_frames == 0
    assert snapshot.statistics.total_signal_updates == 0
    assert snapshot.statistics.latest_timestamp_microseconds is None

    for invalid in (0, -1):
        with pytest.raises(ValueError, match="positive"):
            TelemetryEngine(catalog, invalid)
    with pytest.raises(TypeError, match="integer"):
        TelemetryEngine(catalog, True)


def test_same_frame_signals_share_sequence_timestamp_and_provenance(
    catalog: SignalCatalog,
) -> None:
    engine = TelemetryEngine(catalog)
    samples = engine.ingest(_fast(100))

    assert len(samples) == 4
    assert {sample.timestamp_microseconds for sample in samples} == {100}
    assert {sample.frame_sequence for sample in samples} == {0}
    assert {sample.arbitration_id for sample in samples} == {0x500}
    assert {sample.message_name for sample in samples} == {"DmeFastEngine"}
    assert {sample.source_ecu for sample in samples} == {"TunerOsSimulatedDme"}
    assert {sample.key.signal_name for sample in samples} == {
        "EngineSpeedRpm",
        "ThrottlePosition",
        "EngineLoad",
        "EngineRunning",
    }
    assert type(engine.latest(SignalKey("DmeFastEngine", "EngineRunning")).value) is bool
    assert engine.statistics().total_frames == 1
    assert engine.statistics().total_signal_updates == 4
    assert engine.statistics().frames_by_arbitration_id == {0x500: 1}


def test_same_timestamps_and_duplicates_preserve_arrival_order(catalog: SignalCatalog) -> None:
    engine = TelemetryEngine(catalog)
    first = engine.ingest(_fast(100, 750.0))
    second = engine.ingest(_motion(100, 1.0, 1))
    third = engine.ingest(_fast(100, 750.0))

    assert (first[0].frame_sequence, second[0].frame_sequence, third[0].frame_sequence) == (0, 1, 2)
    rpm_history = engine.history(SignalKey("DmeFastEngine", "EngineSpeedRpm"))
    assert [sample.frame_sequence for sample in rpm_history] == [0, 2]
    assert type(second[1].value) is int
    assert engine.statistics().total_frames == 3


def test_out_of_order_frame_is_rejected_without_partial_mutation(catalog: SignalCatalog) -> None:
    engine = TelemetryEngine(catalog)
    engine.ingest(_fast(100))
    engine.ingest(_motion(100))
    engine.ingest(_thermal(120))
    before = engine.snapshot()

    with pytest.raises(OutOfOrderTelemetryError, match="110.*120"):
        engine.ingest(_fast(110))

    assert engine.snapshot() == before


def test_schema_failure_is_atomic(catalog: SignalCatalog) -> None:
    engine = TelemetryEngine(catalog)
    before = engine.snapshot()
    invalid = DecodedCanFrame(
        0x500,
        "DmeFastEngine",
        0,
        {"EngineSpeedRpm": 750.0, "UnknownSignal": 1.0},
    )
    with pytest.raises(TelemetrySchemaError, match="UnknownSignal"):
        engine.ingest(invalid)
    assert engine.snapshot() == before


def test_bounded_history_rollover_is_oldest_to_newest(catalog: SignalCatalog) -> None:
    engine = TelemetryEngine(catalog, history_capacity=3)
    key = SignalKey("DmeFastEngine", "EngineSpeedRpm")
    for sequence in range(5):
        engine.ingest(
            DecodedCanFrame(0x500, "DmeFastEngine", sequence, {"EngineSpeedRpm": sequence + 1.0})
        )

    history = engine.history(key)
    assert [sample.value for sample in history] == [3.0, 4.0, 5.0]
    assert [sample.frame_sequence for sample in history] == [2, 3, 4]
    assert engine.latest(key) == history[-1]


def test_multirate_freshness_uses_simulation_time_and_exact_threshold(
    catalog: SignalCatalog,
) -> None:
    engine = TelemetryEngine(catalog)
    rpm_key = SignalKey("DmeFastEngine", "EngineSpeedRpm")
    coolant_key = SignalKey("DmeThermalElectrical", "CoolantTemperature")
    engine.ingest(_fast(0))
    engine.ingest(_thermal(0))

    assert engine.freshness(rpm_key, 20_000) is SignalFreshness.FRESH
    assert engine.freshness(rpm_key, 20_001) is SignalFreshness.STALE
    engine.ingest(_motion(30_001))
    snapshot = engine.snapshot()
    assert snapshot.observation_timestamp_microseconds == 30_001
    assert snapshot.status(rpm_key) is SignalFreshness.STALE
    assert snapshot.status(coolant_key) is SignalFreshness.FRESH
    assert snapshot.latest(rpm_key) is not None


def test_snapshots_statistics_and_history_cannot_mutate_engine(catalog: SignalCatalog) -> None:
    engine = TelemetryEngine(catalog)
    rpm_key = SignalKey("DmeFastEngine", "EngineSpeedRpm")
    engine.ingest(_fast(0))
    snapshot = engine.snapshot([rpm_key])
    history = engine.history(rpm_key)
    statistics = engine.statistics()

    with pytest.raises(TypeError):
        snapshot.samples[rpm_key] = history[0]  # type: ignore[index]
    with pytest.raises(TypeError):
        statistics.frames_by_arbitration_id[0x500] = 99  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        history[0].value = 1.0  # type: ignore[misc]

    engine.ingest(_fast(10_000, 800.0))
    assert snapshot.latest(rpm_key).value == 750.0
    assert len(history) == 1
    assert engine.latest(rpm_key).value == 800.0


def test_reset_and_reingestion_are_exactly_reproducible(catalog: SignalCatalog) -> None:
    engine = TelemetryEngine(catalog, history_capacity=8)
    frames = [_fast(0), _thermal(0), _motion(0), _fast(10_000, 760.0), _motion(20_000, 0.5, 1)]
    keys = (
        SignalKey("DmeFastEngine", "EngineSpeedRpm"),
        SignalKey("DscVehicleMotion", "VehicleSpeed"),
    )
    for frame in frames:
        engine.ingest(frame)
    first = (engine.snapshot(), tuple(engine.history(key) for key in keys), engine.statistics())

    engine.reset()
    assert engine.snapshot().samples == {}
    assert engine.statistics().total_frames == 0
    for frame in frames:
        engine.ingest(frame)
    second = (engine.snapshot(), tuple(engine.history(key) for key in keys), engine.statistics())

    assert second == first
