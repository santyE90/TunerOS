import pytest
from tuneros.can import (
    CanDatabaseMetadata,
    CanMessageMetadata,
    CanSignalMetadata,
    DecodedCanFrame,
    TunerOsDbcDecoder,
)
from tuneros.telemetry import SignalCatalog, SignalKey, TelemetrySchemaError


def _catalog() -> SignalCatalog:
    return SignalCatalog(TunerOsDbcDecoder().database_metadata)


def test_catalog_discovers_every_current_dbc_signal_and_provenance() -> None:
    catalog = _catalog()
    assert len(catalog.definitions) == 19

    engine_speed = catalog.require(SignalKey("DmeFastEngine", "EngineSpeedRpm"))
    assert engine_speed.arbitration_id == 0x500
    assert engine_speed.source_ecu == "TunerOsSimulatedDme"
    assert engine_speed.unit == "rpm"
    assert engine_speed.expected_period_microseconds == 10_000

    vehicle_speed = catalog.require(SignalKey("DscVehicleMotion", "VehicleSpeed"))
    assert vehicle_speed.arbitration_id == 0x520
    assert vehicle_speed.source_ecu == "TunerOsSimulatedDsc"
    assert vehicle_speed.unit == "m/s"
    assert vehicle_speed.expected_period_microseconds == 20_000

    assert {definition.message_name for definition in catalog.definitions} == {
        "DmeFastEngine",
        "DmeAirLoad",
        "DmeThermalElectrical",
        "DmeCombustionObservation",
        "DscVehicleMotion",
        "DscWheelSpeeds",
    }


def test_unique_signal_name_lookup_is_ergonomic_and_explicitly_ambiguous() -> None:
    catalog = _catalog()
    assert catalog.find_unique_signal("EngineSpeedRpm") == SignalKey(
        "DmeFastEngine", "EngineSpeedRpm"
    )
    assert catalog.find_unique_signal("DoesNotExist") is None

    ambiguous_metadata = CanDatabaseMetadata(
        messages=(
            CanMessageMetadata(1, "First", "EcuA", 10_000, (CanSignalMetadata("Speed", "m/s"),)),
            CanMessageMetadata(2, "Second", "EcuB", 20_000, (CanSignalMetadata("Speed", "m/s"),)),
        )
    )
    ambiguous = SignalCatalog(ambiguous_metadata)
    with pytest.raises(TelemetrySchemaError, match="ambiguous"):
        ambiguous.find_unique_signal("Speed")


@pytest.mark.parametrize(
    "frame,match",
    [
        (DecodedCanFrame(0x600, "Unknown", 0, {"Signal": 1.0}), "unknown arbitration"),
        (DecodedCanFrame(0x500, "WrongName", 0, {"EngineSpeedRpm": 1.0}), "not WrongName"),
        (DecodedCanFrame(0x500, "DmeFastEngine", 0, {"Unknown": 1.0}), "not defined"),
    ],
)
def test_catalog_rejects_inconsistent_manually_constructed_frames(
    frame: DecodedCanFrame, match: str
) -> None:
    with pytest.raises(TelemetrySchemaError, match=match):
        _catalog().definitions_for_frame(frame)
