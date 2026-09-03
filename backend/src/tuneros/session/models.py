"""Immutable manifest contracts for TunerOS session format version 1."""

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Self
from uuid import UUID

from tuneros.session.errors import SessionFormatError, SessionVersionError

SESSION_FORMAT_NAME = "tuneros.raw_can_session"
SESSION_FORMAT_VERSION = 1
SESSION_FORMAT_VERSION_CALIBRATION = 2
REFERENCE_VEHICLE_PROFILE_ID = "bmw-e90-335i-n54-2010-manual"
SYNTHETIC_CAN_NETWORK = "TunerOS synthetic Classic CAN"


class SessionStatus(StrEnum):
    RECORDING = "recording"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class SessionManifest:
    format_name: str
    format_version: int
    session_id: str
    created_at_utc: str
    name: str | None
    scenario: str | None
    vehicle_profile_id: str
    can_network: str
    dbc_name: str
    dbc_sha256: str
    frames_sha256: str | None
    status: SessionStatus
    failure_reason: str | None
    frame_count: int
    first_timestamp_microseconds: int | None
    last_timestamp_microseconds: int | None
    duration_microseconds: int
    calibration_id: str | None = None
    calibration_revision: int | None = None

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        if self.format_version == SESSION_FORMAT_VERSION:
            value.pop("calibration_id")
            value.pop("calibration_revision")
        return value

    @classmethod
    def from_dict(cls, value: object) -> Self:
        if not isinstance(value, dict):
            raise SessionFormatError("session manifest must be a JSON object")
        version = value.get("format_version")
        if type(version) is not int or version not in (
            SESSION_FORMAT_VERSION,
            SESSION_FORMAT_VERSION_CALIBRATION,
        ):
            raise SessionVersionError(f"unsupported session format version {version!r}")
        expected = set(cls.__dataclass_fields__)
        if version == SESSION_FORMAT_VERSION:
            expected -= {"calibration_id", "calibration_revision"}
        if set(value) != expected:
            missing = sorted(expected - set(value))
            extra = sorted(set(value) - expected)
            raise SessionFormatError(
                f"session manifest fields mismatch: missing={missing}, extra={extra}"
            )
        if value["format_name"] != SESSION_FORMAT_NAME:
            raise SessionFormatError(f"unsupported session format {value['format_name']!r}")
        try:
            manifest = cls(
                format_name=value["format_name"],
                format_version=version,
                session_id=_string(value, "session_id"),
                created_at_utc=_string(value, "created_at_utc"),
                name=_optional_string(value, "name"),
                scenario=_optional_string(value, "scenario"),
                vehicle_profile_id=_string(value, "vehicle_profile_id"),
                can_network=_string(value, "can_network"),
                dbc_name=_string(value, "dbc_name"),
                dbc_sha256=_hash(value, "dbc_sha256"),
                frames_sha256=(
                    None if value["frames_sha256"] is None else _hash(value, "frames_sha256")
                ),
                status=SessionStatus(value["status"]),
                failure_reason=_optional_string(value, "failure_reason"),
                frame_count=_nonnegative_integer(value, "frame_count"),
                first_timestamp_microseconds=_optional_nonnegative_integer(
                    value, "first_timestamp_microseconds"
                ),
                last_timestamp_microseconds=_optional_nonnegative_integer(
                    value, "last_timestamp_microseconds"
                ),
                duration_microseconds=_nonnegative_integer(value, "duration_microseconds"),
                calibration_id=(
                    None if version == SESSION_FORMAT_VERSION else _string(value, "calibration_id")
                ),
                calibration_revision=(
                    None
                    if version == SESSION_FORMAT_VERSION
                    else _positive_integer(value, "calibration_revision")
                ),
            )
        except (TypeError, ValueError) as error:
            raise SessionFormatError(f"invalid session manifest: {error}") from error
        manifest._validate_consistency()
        return manifest

    def _validate_consistency(self) -> None:
        try:
            if str(UUID(self.session_id)) != self.session_id:
                raise ValueError
        except ValueError as error:
            raise SessionFormatError("session_id must be a canonical UUID") from error
        if self.frame_count == 0:
            if (
                self.first_timestamp_microseconds is not None
                or self.last_timestamp_microseconds is not None
            ):
                raise SessionFormatError("empty session timestamps must be null")
            if self.duration_microseconds != 0:
                raise SessionFormatError("empty session duration must be zero")
        else:
            if (
                self.first_timestamp_microseconds is None
                or self.last_timestamp_microseconds is None
            ):
                raise SessionFormatError("non-empty session timestamps cannot be null")
            if self.last_timestamp_microseconds < self.first_timestamp_microseconds:
                raise SessionFormatError("last timestamp precedes first timestamp")
            if self.duration_microseconds != (
                self.last_timestamp_microseconds - self.first_timestamp_microseconds
            ):
                raise SessionFormatError("session duration does not match timestamps")
        if self.status is SessionStatus.RECORDING:
            if self.frames_sha256 is not None or self.failure_reason is not None:
                raise SessionFormatError("recording session cannot have a hash or failure reason")
        elif self.status is SessionStatus.COMPLETE:
            if self.frames_sha256 is None:
                raise SessionFormatError("complete session requires frames_sha256")
            if self.failure_reason is not None:
                raise SessionFormatError("complete session cannot have a failure reason")
        elif self.frames_sha256 is None or not self.failure_reason:
            raise SessionFormatError("incomplete session requires a hash and failure reason")
        if self.format_version == SESSION_FORMAT_VERSION:
            if self.calibration_id is not None or self.calibration_revision is not None:
                raise SessionFormatError("version 1 sessions cannot contain calibration metadata")
        elif not self.calibration_id or self.calibration_revision is None:
            raise SessionFormatError("version 2 sessions require calibration provenance")


def _string(value: dict[object, object], key: str) -> str:
    item = value[key]
    if not isinstance(item, str) or not item:
        raise TypeError(f"{key} must be a non-empty string")
    return item


def _optional_string(value: dict[object, object], key: str) -> str | None:
    item = value[key]
    if item is not None and not isinstance(item, str):
        raise TypeError(f"{key} must be a string or null")
    return item


def _nonnegative_integer(value: dict[object, object], key: str) -> int:
    item = value[key]
    if type(item) is not int or item < 0:
        raise TypeError(f"{key} must be a non-negative integer")
    return item


def _positive_integer(value: dict[object, object], key: str) -> int:
    item = _nonnegative_integer(value, key)
    if item == 0:
        raise TypeError(f"{key} must be a positive integer")
    return item


def _optional_nonnegative_integer(value: dict[object, object], key: str) -> int | None:
    item = value[key]
    return None if item is None else _nonnegative_integer(value, key)


def _hash(value: dict[object, object], key: str) -> str:
    item = _string(value, key)
    if len(item) != 64 or any(character not in "0123456789abcdef" for character in item):
        raise TypeError(f"{key} must be a lowercase SHA-256 hex digest")
    return item
