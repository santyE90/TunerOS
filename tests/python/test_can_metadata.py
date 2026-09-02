from tuneros.can import TunerOsDbcDecoder


def test_decoder_exposes_library_independent_authoritative_metadata() -> None:
    metadata = TunerOsDbcDecoder().database_metadata
    messages = {message.arbitration_id: message for message in metadata.messages}

    assert tuple(messages) == (0x500, 0x501, 0x502, 0x520, 0x521)
    expected = {
        0x500: (
            "DmeFastEngine",
            "TunerOsSimulatedDme",
            10_000,
            (
                ("EngineSpeedRpm", "rpm"),
                ("ThrottlePosition", "normalized"),
                ("EngineLoad", "normalized"),
                ("EngineRunning", "boolean"),
            ),
        ),
        0x501: (
            "DmeAirLoad",
            "TunerOsSimulatedDme",
            20_000,
            (
                ("ManifoldPressureAbsolute", "kPa_abs"),
                ("AcceleratorPedalPosition", "normalized"),
                ("RequestedScenarioLoad", "normalized"),
            ),
        ),
        0x502: (
            "DmeThermalElectrical",
            "TunerOsSimulatedDme",
            100_000,
            (
                ("CoolantTemperature", "degC"),
                ("OilTemperature", "degC"),
                ("IntakeAirTemperature", "degC"),
                ("BatteryVoltage", "V"),
            ),
        ),
        0x520: (
            "DscVehicleMotion",
            "TunerOsSimulatedDsc",
            20_000,
            (("VehicleSpeed", "m/s"), ("CurrentGear", "gear")),
        ),
        0x521: (
            "DscWheelSpeeds",
            "TunerOsSimulatedDsc",
            20_000,
            (
                ("FrontLeftWheelSpeed", "m/s"),
                ("FrontRightWheelSpeed", "m/s"),
                ("RearLeftWheelSpeed", "m/s"),
                ("RearRightWheelSpeed", "m/s"),
            ),
        ),
    }
    actual = {
        arbitration_id: (
            message.message_name,
            message.transmitter,
            message.cycle_time_microseconds,
            tuple((signal.signal_name, signal.unit) for signal in message.signals),
        )
        for arbitration_id, message in messages.items()
    }
    assert actual == expected


def test_metadata_models_are_immutable() -> None:
    message = TunerOsDbcDecoder().database_metadata.messages[0]
    assert isinstance(message.signals, tuple)
    assert message.signals[0].unit == "rpm"
