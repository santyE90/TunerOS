import json
from pathlib import Path

import pytest
from tuneros.can import (
    MalformedCanFrameError,
    RawCanFrame,
    TunerOsDbcDecoder,
    UnknownCanFrameError,
)

_FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "can" / "golden_frames.json"
_RESOLUTIONS = {
    "EngineSpeedRpm": 0.25,
    "ThrottlePosition": 1.0 / 255.0,
    "EngineLoad": 1.0 / 255.0,
    "ManifoldPressureAbsolute": 0.1,
    "AcceleratorPedalPosition": 1.0 / 255.0,
    "RequestedScenarioLoad": 1.0 / 255.0,
    "CoolantTemperature": 0.1,
    "OilTemperature": 0.1,
    "IntakeAirTemperature": 0.1,
    "BatteryVoltage": 0.1,
    "VehicleSpeed": 0.01,
    "CurrentGear": 1.0,
    "FrontLeftWheelSpeed": 0.01,
    "FrontRightWheelSpeed": 0.01,
    "RearLeftWheelSpeed": 0.01,
    "RearRightWheelSpeed": 0.01,
}


def _golden_vectors() -> list[dict]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))["vectors"]


@pytest.fixture(scope="module")
def decoder() -> TunerOsDbcDecoder:
    return TunerOsDbcDecoder()


@pytest.mark.parametrize("vector", _golden_vectors(), ids=lambda vector: vector["name"])
def test_golden_wire_vectors_decode_to_quantized_engineering_values(
    decoder: TunerOsDbcDecoder, vector: dict
) -> None:
    raw = RawCanFrame(
        vector["arbitration_id"],
        bytes.fromhex(vector["payload_hex"]),
        vector["timestamp_microseconds"],
    )
    decoded = decoder.decode(raw)

    assert decoded.arbitration_id == vector["arbitration_id"]
    assert decoded.timestamp_microseconds == vector["timestamp_microseconds"]
    assert set(decoded.signals) == set(vector["expected"])
    for signal_name, expected in vector["expected"].items():
        actual = decoded.signals[signal_name]
        if isinstance(expected, bool):
            assert actual is expected
        else:
            resolution = _RESOLUTIONS[signal_name]
            assert actual == pytest.approx(expected, abs=resolution / 1_000_000)


def test_decoder_registry_and_unknown_id_policy(decoder: TunerOsDbcDecoder) -> None:
    assert decoder.supported_arbitration_ids == (0x500, 0x501, 0x502, 0x503, 0x520, 0x521)
    assert decoder.supports(0x500)
    assert not decoder.supports(0x600)
    assert decoder.message_name(0x502) == "DmeThermalElectrical"
    assert decoder.message_name(0x520) == "DscVehicleMotion"
    assert decoder.message_name(0x521) == "DscWheelSpeeds"

    with pytest.raises(UnknownCanFrameError, match="0x600"):
        decoder.decode(RawCanFrame(0x600, b"\x00", 1))
    with pytest.raises(UnknownCanFrameError, match="0x600"):
        decoder.message_name(0x600)


@pytest.mark.parametrize(
    "arbitration_id,dlc",
    [(0x500, 5), (0x501, 4), (0x502, 7), (0x503, 3), (0x520, 3), (0x521, 8)],
)
def test_known_frames_require_exact_dlc(
    decoder: TunerOsDbcDecoder, arbitration_id: int, dlc: int
) -> None:
    with pytest.raises(MalformedCanFrameError, match="requires DLC"):
        decoder.decode(RawCanFrame(arbitration_id, bytes(dlc - 1), 0))
    if dlc < 8:
        with pytest.raises(MalformedCanFrameError, match="requires DLC"):
            decoder.decode(RawCanFrame(arbitration_id, bytes(dlc + 1), 0))


def test_little_endian_order_is_observable(decoder: TunerOsDbcDecoder) -> None:
    decoded = decoder.decode(RawCanFrame(0x500, bytes.fromhex("3412000001"), 12_345_678))

    assert decoded.signals["EngineSpeedRpm"] == 0x1234 * 0.25
    assert decoded.timestamp_microseconds == 12_345_678


def test_city_samples_show_increasing_load_and_pressure(decoder: TunerOsDbcDecoder) -> None:
    vectors = {vector["name"]: vector for vector in _golden_vectors()}

    def decode_named(name: str):
        vector = vectors[name]
        return decoder.decode(
            RawCanFrame(
                vector["arbitration_id"],
                bytes.fromhex(vector["payload_hex"]),
                vector["timestamp_microseconds"],
            )
        )

    idle_fast = decode_named("city_idle_fast")
    acceleration_fast = decode_named("city_acceleration_fast")
    idle_air = decode_named("city_idle_air_load")
    moderate_air = decode_named("city_moderate_air_load")
    near_ambient_air = decode_named("city_near_ambient_air_load")

    assert acceleration_fast.signals["EngineSpeedRpm"] > idle_fast.signals["EngineSpeedRpm"]
    assert acceleration_fast.signals["ThrottlePosition"] > idle_fast.signals["ThrottlePosition"]
    assert (
        moderate_air.signals["ManifoldPressureAbsolute"]
        > idle_air.signals["ManifoldPressureAbsolute"]
    )
    assert (
        near_ambient_air.signals["ManifoldPressureAbsolute"]
        > moderate_air.signals["ManifoldPressureAbsolute"]
    )


def test_cold_start_samples_show_engine_and_voltage_transition(
    decoder: TunerOsDbcDecoder,
) -> None:
    vectors = {vector["name"]: vector for vector in _golden_vectors()}

    def decode_named(name: str):
        vector = vectors[name]
        return decoder.decode(
            RawCanFrame(
                vector["arbitration_id"],
                bytes.fromhex(vector["payload_hex"]),
                vector["timestamp_microseconds"],
            )
        )

    before_fast = decode_named("cold_before_start_fast")
    after_fast = decode_named("cold_after_start_fast")
    before_thermal = decode_named("cold_before_start_thermal")
    after_thermal = decode_named("cold_after_start_thermal")

    assert before_fast.signals["EngineRunning"] is False
    assert before_fast.signals["EngineSpeedRpm"] == 0.0
    assert after_fast.signals["EngineRunning"] is True
    assert after_fast.signals["EngineSpeedRpm"] > 0.0
    assert after_thermal.signals["BatteryVoltage"] > before_thermal.signals["BatteryVoltage"]


def test_dsc_golden_samples_preserve_speed_quantization_and_wheel_consistency(
    decoder: TunerOsDbcDecoder,
) -> None:
    vectors = {vector["name"]: vector for vector in _golden_vectors()}

    def decode_named(name: str):
        vector = vectors[name]
        return decoder.decode(
            RawCanFrame(
                vector["arbitration_id"],
                bytes.fromhex(vector["payload_hex"]),
                vector["timestamp_microseconds"],
            )
        )

    for prefix in ("dsc_zero", "dsc_representative", "dsc_higher"):
        motion = decode_named(f"{prefix}_motion")
        wheels = decode_named(f"{prefix}_wheels")
        assert motion.message_name == "DscVehicleMotion"
        assert wheels.message_name == "DscWheelSpeeds"
        for signal in (
            "FrontLeftWheelSpeed",
            "FrontRightWheelSpeed",
            "RearLeftWheelSpeed",
            "RearRightWheelSpeed",
        ):
            assert wheels.signals[signal] == pytest.approx(
                motion.signals["VehicleSpeed"], abs=0.01 / 1_000_000
            )
