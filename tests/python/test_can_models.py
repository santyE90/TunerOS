import pytest
from tuneros.can import DecodedCanFrame, RawCanFrame


def test_raw_can_frame_accepts_canonical_values() -> None:
    frame = RawCanFrame(0x500, b"\x01\x02", 12_345_678)

    assert frame.arbitration_id == 0x500
    assert frame.payload == b"\x01\x02"
    assert frame.payload_length == 2
    assert frame.timestamp_microseconds == 12_345_678
    assert frame == RawCanFrame(0x500, b"\x01\x02", 12_345_678)
    assert RawCanFrame(0, b"", 0).payload_length == 0


@pytest.mark.parametrize("arbitration_id", [-1, 0x800])
def test_raw_can_frame_rejects_out_of_range_standard_ids(arbitration_id: int) -> None:
    with pytest.raises(ValueError, match="arbitration_id"):
        RawCanFrame(arbitration_id, b"", 0)


def test_raw_can_frame_rejects_invalid_payload_and_timestamp() -> None:
    with pytest.raises(ValueError, match="8 bytes"):
        RawCanFrame(0x500, bytes(9), 0)
    with pytest.raises(TypeError, match="payload must be bytes"):
        RawCanFrame(0x500, bytearray(2), 0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="cannot be negative"):
        RawCanFrame(0x500, b"", -1)


def test_decoded_signals_are_an_immutable_snapshot() -> None:
    source = {"EngineSpeedRpm": 750.0}
    decoded = DecodedCanFrame(0x500, "DmeFastEngine", 10, source)
    source["EngineSpeedRpm"] = 900.0

    assert decoded.signals["EngineSpeedRpm"] == 750.0
    with pytest.raises(TypeError):
        decoded.signals["EngineSpeedRpm"] = 800.0  # type: ignore[index]
