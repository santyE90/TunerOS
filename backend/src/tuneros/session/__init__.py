"""Portable raw-CAN recording and deterministic replay."""

from tuneros.session.catalog import SessionCatalog
from tuneros.session.errors import (
    SessionDbcMismatchError,
    SessionError,
    SessionFormatError,
    SessionIntegrityError,
    SessionRecordingError,
    SessionVersionError,
)
from tuneros.session.format import (
    FRAMES_FILENAME,
    MANIFEST_FILENAME,
    SESSION_FILE_HEADER_SIZE,
    SESSION_FILE_MAGIC,
    decode_session_header,
    encode_session_header,
)
from tuneros.session.models import (
    REFERENCE_VEHICLE_PROFILE_ID,
    SESSION_FORMAT_NAME,
    SESSION_FORMAT_VERSION,
    SESSION_FORMAT_VERSION_CALIBRATION,
    SYNTHETIC_CAN_NETWORK,
    SessionManifest,
    SessionStatus,
)
from tuneros.session.reader import SessionReader
from tuneros.session.recorder import DEFAULT_SESSION_ROOT, SessionRecorder, normalize_session_name
from tuneros.session.replay import SessionReplayResult, replay_session

__all__ = [
    "DEFAULT_SESSION_ROOT",
    "FRAMES_FILENAME",
    "MANIFEST_FILENAME",
    "REFERENCE_VEHICLE_PROFILE_ID",
    "SESSION_FILE_HEADER_SIZE",
    "SESSION_FILE_MAGIC",
    "SESSION_FORMAT_NAME",
    "SESSION_FORMAT_VERSION",
    "SESSION_FORMAT_VERSION_CALIBRATION",
    "SYNTHETIC_CAN_NETWORK",
    "SessionCatalog",
    "SessionDbcMismatchError",
    "SessionError",
    "SessionFormatError",
    "SessionIntegrityError",
    "SessionManifest",
    "SessionReader",
    "SessionRecorder",
    "SessionRecordingError",
    "SessionReplayResult",
    "SessionStatus",
    "SessionVersionError",
    "decode_session_header",
    "encode_session_header",
    "normalize_session_name",
    "replay_session",
]
