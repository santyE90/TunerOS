from decimal import Decimal
from importlib.resources import as_file, files

import canmatrix.formats


def _load_database():
    resource = files("tuneros.can").joinpath("dbc", "tuneros_simulation.dbc")
    assert resource.is_file()
    with as_file(resource) as path:
        databases = canmatrix.formats.loadp(str(path))
    assert len(databases) == 1
    return next(iter(databases.values()))


def test_authoritative_dbc_message_contract() -> None:
    database = _load_database()
    expected = {
        0x500: ("DmeFastEngine", 5, 10),
        0x501: ("DmeAirLoad", 4, 20),
        0x502: ("DmeThermalElectrical", 7, 100),
    }

    assert len(database.frames) == 3
    for frame in database.frames:
        assert (frame.name, frame.size, frame.cycle_time) == expected[frame.arbitration_id.id]
        assert not frame.arbitration_id.extended


def test_authoritative_dbc_signal_contract() -> None:
    database = _load_database()
    expected = {
        0x500: {
            "EngineSpeedRpm": (0, 16, Decimal("0.25"), Decimal("0"), "rpm"),
            "ThrottlePosition": (
                16,
                8,
                Decimal("0.00392156862745098"),
                Decimal("0"),
                "normalized",
            ),
            "EngineLoad": (
                24,
                8,
                Decimal("0.00392156862745098"),
                Decimal("0"),
                "normalized",
            ),
            "EngineRunning": (32, 1, Decimal("1"), Decimal("0"), "boolean"),
        },
        0x501: {
            "ManifoldPressureAbsolute": (0, 16, Decimal("0.1"), Decimal("0"), "kPa_abs"),
            "AcceleratorPedalPosition": (
                16,
                8,
                Decimal("0.00392156862745098"),
                Decimal("0"),
                "normalized",
            ),
            "RequestedScenarioLoad": (
                24,
                8,
                Decimal("0.00392156862745098"),
                Decimal("0"),
                "normalized",
            ),
        },
        0x502: {
            "CoolantTemperature": (0, 16, Decimal("0.1"), Decimal("-100"), "degC"),
            "OilTemperature": (16, 16, Decimal("0.1"), Decimal("-100"), "degC"),
            "IntakeAirTemperature": (32, 16, Decimal("0.1"), Decimal("-100"), "degC"),
            "BatteryVoltage": (48, 8, Decimal("0.1"), Decimal("0"), "V"),
        },
    }

    for frame in database.frames:
        actual = {
            signal.name: (
                signal.start_bit,
                signal.size,
                signal.factor,
                signal.offset,
                signal.unit,
            )
            for signal in frame.signals
        }
        assert actual == expected[frame.arbitration_id.id]
        assert all(signal.is_little_endian for signal in frame.signals)
        assert all(not signal.is_signed for signal in frame.signals)
