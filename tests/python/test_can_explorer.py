import pytest
from tuneros.can import CanDecodeStatus, CanExplorer, RawCanFrame


def _fast(timestamp: int, payload: bytes = bytes.fromhex("7017804001")) -> RawCanFrame:
    return RawCanFrame(0x500, payload, timestamp)


def test_explorer_annotates_known_frame_from_authoritative_dbc() -> None:
    explorer = CanExplorer(capacity=3)
    observed = explorer.ingest(_fast(123_000))

    assert observed.sequence == 0
    assert observed.raw_frame == _fast(123_000)
    assert observed.message_name == "DmeFastEngine"
    assert observed.source_ecu == "TunerOsSimulatedDme"
    assert observed.expected_period_microseconds == 10_000
    assert observed.decode_status is CanDecodeStatus.DECODED
    assert observed.decode_error is None
    assert [(item.signal_name, item.value, item.unit) for item in observed.decoded_signals] == [
        ("EngineSpeedRpm", 1_500.0, "rpm"),
        ("ThrottlePosition", pytest.approx(0.5019607843137255), "normalized"),
        ("EngineLoad", pytest.approx(0.25098039215686274), "normalized"),
        ("EngineRunning", True, "boolean"),
    ]


def test_unknown_and_decode_error_frames_remain_observable() -> None:
    explorer = CanExplorer()
    unknown_raw = RawCanFrame(0x123, b"\xaa\x00", 10)
    unknown = explorer.ingest(unknown_raw)
    malformed_raw = RawCanFrame(0x500, b"\x01", 20)
    malformed = explorer.ingest(malformed_raw)

    assert unknown.raw_frame is unknown_raw
    assert unknown.decode_status is CanDecodeStatus.UNKNOWN
    assert unknown.message_name is None
    assert unknown.source_ecu is None
    assert unknown.decoded_signals == ()
    assert malformed.raw_frame is malformed_raw
    assert malformed.decode_status is CanDecodeStatus.ERROR
    assert malformed.message_name == "DmeFastEngine"
    assert "requires DLC 5" in (malformed.decode_error or "")
    assert malformed.decoded_signals == ()


def test_bounded_rollover_duplicates_filters_detail_and_reset() -> None:
    explorer = CanExplorer(capacity=3)
    frames = (
        _fast(0),
        _fast(0),
        RawCanFrame(0x123, b"\x03", 10),
        RawCanFrame(0x520, bytes.fromhex("000000"), 20),
        RawCanFrame(0x521, bytes.fromhex("0000000000000000"), 20),
    )
    first_run = tuple(explorer.ingest(frame) for frame in frames)

    assert [item.sequence for item in first_run] == [0, 1, 2, 3, 4]
    assert first_run[0].raw_frame == first_run[1].raw_frame
    assert [item.sequence for item in explorer.frames()] == [2, 3, 4]
    assert [item.sequence for item in explorer.frames(limit=1)] == [4]
    assert [item.sequence for item in explorer.frames(arbitration_id=0x520)] == [3]
    assert [item.sequence for item in explorer.frames(message_name="DscWheelSpeeds")] == [4]
    assert [item.sequence for item in explorer.frames(source_ecu="TunerOsSimulatedDsc")] == [3, 4]
    assert explorer.frame(1) is None
    assert explorer.frame(3) == first_run[3]
    assert explorer.statistics().retained_frame_count == 3
    assert explorer.statistics().total_frame_count == 5
    assert explorer.statistics().unique_id_count == 4
    messages = {item.arbitration_id: item for item in explorer.message_statistics()}
    assert messages[0x500].retained_frame_count == 0
    assert messages[0x500].total_frame_count == 2
    assert messages[0x123].retained_frame_count == 1

    explorer.reset()
    assert explorer.snapshot().frames == ()
    assert explorer.statistics().total_frame_count == 0
    second_run = tuple(explorer.ingest(frame) for frame in frames)
    assert second_run == first_run


def test_message_statistics_use_simulation_time() -> None:
    explorer = CanExplorer()
    explorer.ingest(_fast(0))
    explorer.ingest(_fast(10_000))
    explorer.ingest(_fast(20_000))
    statistics = explorer.message_statistic(0x500)

    assert statistics.retained_frame_count == 3
    assert statistics.total_frame_count == 3
    assert statistics.first_timestamp_microseconds == 0
    assert statistics.latest_timestamp_microseconds == 20_000
    assert statistics.expected_period_microseconds == 10_000
    assert statistics.observed_average_period_microseconds == 10_000.0
    assert statistics.observed_frequency_hz == 100.0
    assert statistics.latest_dlc == 5


def test_same_timestamp_period_is_zero_and_frequency_is_undefined() -> None:
    explorer = CanExplorer()
    explorer.ingest(_fast(0))
    explorer.ingest(_fast(0))

    statistics = explorer.message_statistic(0x500)
    assert statistics.observed_average_period_microseconds == 0.0
    assert statistics.observed_frequency_hz is None


@pytest.mark.parametrize("capacity", [True, 0, -1])
def test_explorer_rejects_invalid_capacity(capacity: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        CanExplorer(capacity=capacity)  # type: ignore[arg-type]
