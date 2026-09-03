"""Read-only public metadata for the authoritative C++ synthetic calibration profiles."""

from dataclasses import dataclass

SYNTHETIC_CALIBRATION_DISCLAIMER = (
    "Synthetic TunerOS simulation calibration. Not BMW factory data and not suitable for "
    "flashing or real-vehicle tuning."
)


@dataclass(frozen=True, slots=True)
class CalibrationAxis:
    name: str
    unit: str
    breakpoints: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class CalibrationTable:
    table_id: str
    name: str
    value_unit: str
    row_axis: CalibrationAxis
    column_axis: CalibrationAxis | None
    values: tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class CalibrationParameter:
    name: str
    value: float
    unit: str


@dataclass(frozen=True, slots=True)
class CalibrationProfile:
    profile_id: str
    display_name: str
    revision: int
    description: str
    synthetic: bool
    disclaimer: str
    parameters: tuple[CalibrationParameter, ...]
    tables: tuple[CalibrationTable, ...]


def _axis(name: str, unit: str, *values: float) -> CalibrationAxis:
    return CalibrationAxis(name, unit, values)


def _table1d(
    table_id: str,
    name: str,
    unit: str,
    axis: CalibrationAxis,
    values: tuple[float, ...],
) -> CalibrationTable:
    return CalibrationTable(table_id, name, unit, axis, None, (values,))


def _table2d(
    table_id: str,
    name: str,
    unit: str,
    rows: CalibrationAxis,
    columns: CalibrationAxis,
    values: tuple[tuple[float, ...], ...],
) -> CalibrationTable:
    return CalibrationTable(table_id, name, unit, rows, columns, values)


_PEDAL = _axis("Pedal", "normalized", 0.0, 0.25, 0.5, 0.75, 1.0)
_BOOST_RPM = _axis("Engine speed", "rpm", 1_000.0, 2_500.0, 4_000.0, 5_500.0, 6_500.0)
_LOAD_3 = _axis("Load", "normalized", 0.0, 0.5, 1.0)
_LAMBDA_LOAD = _axis("Load", "normalized", 0.0, 0.5, 0.8, 1.0)
_IGNITION_RPM = _axis("Engine speed", "rpm", 2_000.0, 3_500.0, 5_000.0, 6_500.0)


def _profile(profile_id: str) -> CalibrationProfile:
    stage1 = profile_id == "stage-1"
    return CalibrationProfile(
        profile_id=profile_id,
        display_name="Stage 1" if stage1 else "Stock",
        revision=1,
        description=(
            "TunerOS synthetic higher-output simulation calibration; not real tuning data."
            if stage1
            else "TunerOS synthetic baseline calibration for the simulated N54 powertrain."
        ),
        synthetic=True,
        disclaimer=SYNTHETIC_CALIBRATION_DISCLAIMER,
        parameters=(
            CalibrationParameter("Boost response time constant", 0.65 if stage1 else 0.80, "s"),
            CalibrationParameter("Engine output multiplier", 1.08 if stage1 else 1.0, "ratio"),
        ),
        tables=(
            _table1d(
                "throttle-response",
                "Throttle response",
                "normalized load",
                _PEDAL,
                (0.0, 0.28, 0.60, 0.86, 1.0) if stage1 else (0.0, 0.22, 0.48, 0.74, 1.0),
            ),
            _table2d(
                "boost-target",
                "Boost target",
                "kPa_gauge",
                _BOOST_RPM,
                _LOAD_3,
                (
                    (
                        (0.0, 0.0, 0.0),
                        (0.0, 35.0, 95.0),
                        (0.0, 50.0, 125.0),
                        (0.0, 45.0, 110.0),
                        (0.0, 20.0, 65.0),
                    )
                    if stage1
                    else (
                        (0.0, 0.0, 0.0),
                        (0.0, 25.0, 70.0),
                        (0.0, 35.0, 90.0),
                        (0.0, 28.0, 75.0),
                        (0.0, 10.0, 40.0),
                    )
                ),
            ),
            _table1d(
                "lambda-target",
                "Lambda target",
                "lambda",
                _LAMBDA_LOAD,
                (1.0, 1.0, 0.88, 0.82) if stage1 else (1.0, 1.0, 0.90, 0.86),
            ),
            _table2d(
                "ignition-target",
                "Ignition target",
                "degrees",
                _IGNITION_RPM,
                _LOAD_3,
                (
                    ((18.0, 14.0, 9.0), (22.0, 16.0, 10.0), (24.0, 18.0, 9.0), (20.0, 14.0, 7.0))
                    if stage1
                    else (
                        (18.0, 14.0, 10.0),
                        (22.0, 15.0, 8.0),
                        (24.0, 16.0, 7.0),
                        (20.0, 12.0, 5.0),
                    )
                ),
            ),
        ),
    )


CALIBRATION_PROFILES = (_profile("stock"), _profile("stage-1"))


def calibration_profiles() -> tuple[CalibrationProfile, ...]:
    return CALIBRATION_PROFILES


def calibration_profile(profile_id: str) -> CalibrationProfile:
    for profile in CALIBRATION_PROFILES:
        if profile.profile_id == profile_id:
            return profile
    raise KeyError(f"unknown calibration profile {profile_id!r}")
