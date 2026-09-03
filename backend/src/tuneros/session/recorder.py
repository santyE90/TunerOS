"""Incremental synchronous raw-CAN session recorder."""

import hashlib
import os
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from tuneros.can import (
    AUTHORITATIVE_DBC_NAME,
    RawCanFrame,
    authoritative_dbc_sha256,
    encode_raw_can_record,
)
from tuneros.session.errors import SessionRecordingError
from tuneros.session.format import (
    FRAMES_FILENAME,
    MANIFEST_FILENAME,
    encode_session_header,
    write_manifest_atomic,
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

DEFAULT_SESSION_ROOT = Path("data/sessions")


def normalize_session_name(name: str | None) -> str | None:
    if name is None:
        return None
    normalized = " ".join(name.split())
    if not normalized:
        raise ValueError("session name cannot be empty")
    if len(normalized) > 120:
        raise ValueError("session name cannot exceed 120 characters")
    if any(ord(character) < 32 for character in normalized):
        raise ValueError("session name cannot contain control characters")
    return normalized


class SessionRecorder:
    """Stream raw frames to a partial artifact and atomically publish on completion."""

    def __init__(
        self,
        session_root: Path = DEFAULT_SESSION_ROOT,
        *,
        name: str | None = None,
        scenario: str | None = None,
        session_id: UUID | None = None,
        created_at_utc: datetime | None = None,
        dbc_name: str = AUTHORITATIVE_DBC_NAME,
        dbc_sha256: str | None = None,
        calibration_id: str | None = None,
        calibration_revision: int | None = None,
    ) -> None:
        identifier = session_id or uuid4()
        created = created_at_utc or datetime.now(UTC)
        if created.tzinfo is None:
            raise ValueError("created_at_utc must be timezone-aware")
        self._session_root = Path(session_root)
        self._session_root.mkdir(parents=True, exist_ok=True)
        self._partial_path = self._session_root / f"{identifier}.partial"
        self._final_path = self._session_root / f"{identifier}.tuneros"
        if self._partial_path.exists() or self._final_path.exists():
            raise SessionRecordingError(f"session {identifier} already exists")
        self._partial_path.mkdir()
        if (calibration_id is None) != (calibration_revision is None):
            raise ValueError("calibration ID and revision must be supplied together")
        if calibration_id is not None and (not calibration_id or not calibration_revision):
            raise ValueError("calibration provenance requires a non-empty ID and positive revision")
        format_version = (
            SESSION_FORMAT_VERSION if calibration_id is None else SESSION_FORMAT_VERSION_CALIBRATION
        )
        self._manifest = SessionManifest(
            format_name=SESSION_FORMAT_NAME,
            format_version=format_version,
            session_id=str(identifier),
            created_at_utc=created.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            name=normalize_session_name(name),
            scenario=normalize_session_name(scenario),
            vehicle_profile_id=REFERENCE_VEHICLE_PROFILE_ID,
            can_network=SYNTHETIC_CAN_NETWORK,
            dbc_name=dbc_name,
            dbc_sha256=dbc_sha256 or authoritative_dbc_sha256(),
            frames_sha256=None,
            status=SessionStatus.RECORDING,
            failure_reason=None,
            frame_count=0,
            first_timestamp_microseconds=None,
            last_timestamp_microseconds=None,
            duration_microseconds=0,
            calibration_id=calibration_id,
            calibration_revision=calibration_revision,
        )
        self._frames_path = self._partial_path / FRAMES_FILENAME
        self._stream = self._frames_path.open("wb")
        self._hasher = hashlib.sha256()
        header = encode_session_header(format_version)
        self._stream.write(header)
        self._hasher.update(header)
        self._closed = False
        write_manifest_atomic(self._partial_path / MANIFEST_FILENAME, self._manifest)

    @property
    def manifest(self) -> SessionManifest:
        return self._manifest

    @property
    def artifact_path(self) -> Path:
        return (
            self._final_path
            if self._manifest.status is SessionStatus.COMPLETE
            else self._partial_path
        )

    @property
    def frame_count(self) -> int:
        return self._manifest.frame_count

    @property
    def recording(self) -> bool:
        return not self._closed and self._manifest.status is SessionStatus.RECORDING

    def record(self, frame: RawCanFrame) -> None:
        if self._closed or self._manifest.status is not SessionStatus.RECORDING:
            raise SessionRecordingError("session recorder is not recording")
        previous = self._manifest.last_timestamp_microseconds
        if previous is not None and frame.timestamp_microseconds < previous:
            raise SessionRecordingError(
                f"raw frame timestamp {frame.timestamp_microseconds} precedes {previous}"
            )
        encoded = encode_raw_can_record(frame)
        try:
            self._stream.write(encoded)
        except OSError as error:
            raise SessionRecordingError("failed writing raw session frame") from error
        self._hasher.update(encoded)
        first = self._manifest.first_timestamp_microseconds
        if first is None:
            first = frame.timestamp_microseconds
        self._manifest = replace(
            self._manifest,
            frame_count=self._manifest.frame_count + 1,
            first_timestamp_microseconds=first,
            last_timestamp_microseconds=frame.timestamp_microseconds,
            duration_microseconds=frame.timestamp_microseconds - first,
        )

    def complete(self) -> SessionManifest:
        if self._closed or self._manifest.status is not SessionStatus.RECORDING:
            raise SessionRecordingError("session recorder cannot be completed")
        self._finish_stream()
        complete_manifest = replace(
            self._manifest,
            frames_sha256=self._hasher.hexdigest(),
            status=SessionStatus.COMPLETE,
        )
        try:
            write_manifest_atomic(self._partial_path / MANIFEST_FILENAME, complete_manifest)
            os.replace(self._partial_path, self._final_path)
        except OSError as error:
            self._manifest = replace(
                complete_manifest,
                status=SessionStatus.INCOMPLETE,
                failure_reason="failed publishing completed session artifact",
            )
            with suppress(OSError):
                write_manifest_atomic(self._partial_path / MANIFEST_FILENAME, self._manifest)
            raise SessionRecordingError("failed publishing completed session artifact") from error
        self._manifest = complete_manifest
        return self._manifest

    def abort(self, reason: str) -> SessionManifest:
        if self._closed:
            return self._manifest
        self._finish_stream()
        safe_reason = reason.strip()[:500] or "recording failed"
        self._manifest = replace(
            self._manifest,
            frames_sha256=self._hasher.hexdigest(),
            status=SessionStatus.INCOMPLETE,
            failure_reason=safe_reason,
        )
        write_manifest_atomic(self._partial_path / MANIFEST_FILENAME, self._manifest)
        return self._manifest

    def close(self) -> None:
        if not self._closed:
            self.abort("recording closed before normal gateway completion")

    def _finish_stream(self) -> None:
        try:
            self._stream.flush()
            os.fsync(self._stream.fileno())
            self._stream.close()
        except OSError as error:
            raise SessionRecordingError("failed finalizing raw session frame file") from error
        finally:
            self._closed = True

    def __enter__(self) -> "SessionRecorder":
        return self

    def __exit__(self, exception_type, exception, traceback) -> None:
        if exception is None:
            self.complete()
        else:
            self.abort(str(exception))
