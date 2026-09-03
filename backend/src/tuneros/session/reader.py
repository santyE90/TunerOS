"""Validated lazy reader for complete raw-CAN session artifacts."""

import hashlib
from collections.abc import Iterator
from pathlib import Path

from tuneros.can import RAW_CAN_RECORD_SIZE, RawCanFrame, RawCanRecordError, decode_raw_can_record
from tuneros.session.errors import (
    SessionDbcMismatchError,
    SessionFormatError,
    SessionIntegrityError,
    SessionVersionError,
)
from tuneros.session.format import (
    FRAMES_FILENAME,
    MANIFEST_FILENAME,
    SESSION_FILE_HEADER_SIZE,
    decode_session_header,
    read_manifest,
)
from tuneros.session.models import SessionManifest, SessionStatus


class SessionReader:
    """Read one complete artifact while preserving bounded memory usage."""

    def __init__(self, artifact_path: Path, *, expected_dbc_sha256: str | None = None) -> None:
        self._artifact_path = Path(artifact_path)
        self._manifest = read_manifest(self._artifact_path / MANIFEST_FILENAME)
        if self._manifest.status is not SessionStatus.COMPLETE:
            raise SessionIntegrityError(
                f"session {self._manifest.session_id} is {self._manifest.status}, not complete"
            )
        if expected_dbc_sha256 is not None and self._manifest.dbc_sha256 != expected_dbc_sha256:
            raise SessionDbcMismatchError(
                "recorded DBC SHA-256 does not match the installed authoritative DBC"
            )
        self._frames_path = self._artifact_path / FRAMES_FILENAME

    @property
    def manifest(self) -> SessionManifest:
        return self._manifest

    @property
    def artifact_path(self) -> Path:
        return self._artifact_path

    def validate_integrity(self) -> None:
        count = 0
        first_timestamp: int | None = None
        last_timestamp: int | None = None
        hasher = hashlib.sha256()
        try:
            with self._frames_path.open("rb") as stream:
                header = stream.read(SESSION_FILE_HEADER_SIZE)
                version = decode_session_header(header)
                if version != self._manifest.format_version:
                    raise SessionVersionError(
                        "session frame version does not match manifest format version"
                    )
                hasher.update(header)
                while True:
                    record = stream.read(RAW_CAN_RECORD_SIZE)
                    if not record:
                        break
                    if len(record) != RAW_CAN_RECORD_SIZE:
                        raise SessionIntegrityError(
                            f"truncated raw frame record: got {len(record)} of "
                            f"{RAW_CAN_RECORD_SIZE} bytes"
                        )
                    hasher.update(record)
                    frame = self._decode_record(record)
                    if first_timestamp is None:
                        first_timestamp = frame.timestamp_microseconds
                    if last_timestamp is not None and frame.timestamp_microseconds < last_timestamp:
                        raise SessionIntegrityError("raw frame timestamps are not nondecreasing")
                    last_timestamp = frame.timestamp_microseconds
                    count += 1
        except FileNotFoundError as error:
            raise SessionFormatError("session frames.bin is missing") from error
        if count != self._manifest.frame_count:
            raise SessionIntegrityError(
                f"manifest frame count {self._manifest.frame_count} does not match "
                f"file count {count}"
            )
        self._validate_manifest_timestamps(first_timestamp, last_timestamp)
        if hasher.hexdigest() != self._manifest.frames_sha256:
            raise SessionIntegrityError("session frame-file SHA-256 mismatch")

    def frames(self) -> Iterator[RawCanFrame]:
        count = 0
        first_timestamp: int | None = None
        last_timestamp: int | None = None
        hasher = hashlib.sha256()
        try:
            with self._frames_path.open("rb") as stream:
                header = stream.read(SESSION_FILE_HEADER_SIZE)
                version = decode_session_header(header)
                if version != self._manifest.format_version:
                    raise SessionVersionError(
                        "session frame version does not match manifest format version"
                    )
                hasher.update(header)
                while True:
                    record = stream.read(RAW_CAN_RECORD_SIZE)
                    if not record:
                        break
                    if len(record) != RAW_CAN_RECORD_SIZE:
                        raise SessionIntegrityError(
                            f"truncated raw frame record: got {len(record)} of "
                            f"{RAW_CAN_RECORD_SIZE} bytes"
                        )
                    hasher.update(record)
                    frame = self._decode_record(record)
                    if first_timestamp is None:
                        first_timestamp = frame.timestamp_microseconds
                    if last_timestamp is not None and frame.timestamp_microseconds < last_timestamp:
                        raise SessionIntegrityError("raw frame timestamps are not nondecreasing")
                    last_timestamp = frame.timestamp_microseconds
                    count += 1
                    yield frame
        except FileNotFoundError as error:
            raise SessionFormatError("session frames.bin is missing") from error
        if count != self._manifest.frame_count:
            raise SessionIntegrityError(
                f"manifest frame count {self._manifest.frame_count} does not match "
                f"file count {count}"
            )
        self._validate_manifest_timestamps(first_timestamp, last_timestamp)
        if hasher.hexdigest() != self._manifest.frames_sha256:
            raise SessionIntegrityError("session frame-file SHA-256 mismatch")

    @staticmethod
    def _decode_record(record: bytes) -> RawCanFrame:
        try:
            return decode_raw_can_record(record)
        except RawCanRecordError as error:
            raise SessionFormatError(str(error)) from error

    def _validate_manifest_timestamps(
        self, first_timestamp: int | None, last_timestamp: int | None
    ) -> None:
        if first_timestamp != self._manifest.first_timestamp_microseconds:
            raise SessionIntegrityError("manifest first timestamp does not match frame file")
        if last_timestamp != self._manifest.last_timestamp_microseconds:
            raise SessionIntegrityError("manifest last timestamp does not match frame file")
