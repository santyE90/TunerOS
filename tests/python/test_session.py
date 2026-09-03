import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from tuneros.can import (
    RAW_CAN_RECORD_SIZE,
    RawCanFrame,
    TunerOsDbcDecoder,
    authoritative_dbc_sha256,
    encode_raw_can_record,
)
from tuneros.investigation import InvestigationService
from tuneros.session import (
    FRAMES_FILENAME,
    MANIFEST_FILENAME,
    SESSION_FILE_HEADER_SIZE,
    SessionCatalog,
    SessionDbcMismatchError,
    SessionFormatError,
    SessionIntegrityError,
    SessionManifest,
    SessionReader,
    SessionRecorder,
    SessionRecordingError,
    SessionStatus,
    SessionVersionError,
    encode_session_header,
    replay_session,
)

SESSION_ID = UUID("12345678-1234-5678-9234-567812345678")
CREATED = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _frames() -> tuple[RawCanFrame, ...]:
    return (
        RawCanFrame(0x500, bytes.fromhex("b80b0f2e01"), 0),
        RawCanFrame(0x500, bytes.fromhex("b80b0f2e01"), 0),
        RawCanFrame(0x520, bytes.fromhex("640001"), 20_000),
    )


def _record(root: Path, *, dbc_sha256: str | None = None) -> SessionReader:
    recorder = SessionRecorder(
        root,
        name="  CITY   baseline  ",
        scenario="city",
        session_id=SESSION_ID,
        created_at_utc=CREATED,
        dbc_sha256=dbc_sha256,
    )
    for frame in _frames():
        recorder.record(frame)
    manifest = recorder.complete()
    assert manifest.status is SessionStatus.COMPLETE
    return SessionReader(recorder.artifact_path)


def _rewrite_manifest(artifact: Path, **changes: object) -> None:
    path = artifact / MANIFEST_FILENAME
    value = json.loads(path.read_text(encoding="utf-8"))
    value.update(changes)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rehash(artifact: Path) -> None:
    _rewrite_manifest(
        artifact,
        frames_sha256=hashlib.sha256((artifact / FRAMES_FILENAME).read_bytes()).hexdigest(),
    )


def test_exact_header_record_manifest_and_round_trip(tmp_path: Path) -> None:
    reader = _record(tmp_path)
    artifact = reader.artifact_path
    frame_bytes = (artifact / FRAMES_FILENAME).read_bytes()

    assert encode_session_header() == bytes.fromhex("54 4e 53 52 01 00 00 00")
    assert frame_bytes[:SESSION_FILE_HEADER_SIZE] == encode_session_header()
    assert frame_bytes[
        SESSION_FILE_HEADER_SIZE : SESSION_FILE_HEADER_SIZE + RAW_CAN_RECORD_SIZE
    ] == (encode_raw_can_record(_frames()[0]))
    assert list(reader.frames()) == list(_frames())
    assert reader.manifest.session_id == str(SESSION_ID)
    assert reader.manifest.created_at_utc == "2026-09-02T12:00:00Z"
    assert reader.manifest.name == "CITY baseline"
    assert reader.manifest.frame_count == 3
    assert reader.manifest.first_timestamp_microseconds == 0
    assert reader.manifest.last_timestamp_microseconds == 20_000
    assert reader.manifest.duration_microseconds == 20_000
    assert reader.manifest.frames_sha256 == hashlib.sha256(frame_bytes).hexdigest()
    assert not (tmp_path / f"{SESSION_ID}.partial").exists()


def test_calibration_provenance_uses_version_two_without_breaking_legacy(tmp_path: Path) -> None:
    calibrated_id = UUID("87654321-4321-4765-8765-876543218765")
    recorder = SessionRecorder(
        tmp_path,
        session_id=calibrated_id,
        created_at_utc=CREATED,
        scenario="wot-pull",
        calibration_id="stage-1",
        calibration_revision=1,
    )
    recorder.record(_frames()[0])
    manifest = recorder.complete()
    reader = SessionReader(recorder.artifact_path)

    assert manifest.format_version == 2
    assert manifest.calibration_id == "stage-1"
    assert manifest.calibration_revision == 1
    assert (reader.artifact_path / FRAMES_FILENAME).read_bytes()[:8] == bytes.fromhex(
        "54 4e 53 52 02 00 00 00"
    )
    assert list(reader.frames()) == [_frames()[0]]
    assert SessionManifest.from_dict(manifest.to_dict()) == manifest


def test_phase_8a_dbc_hash_remains_additively_compatible(tmp_path: Path) -> None:
    legacy_hash = "320239cad283771dcffbcf293ed6d319ee11c4c383ab3da4d680a8dac16306f2"
    reader = _record(tmp_path, dbc_sha256=legacy_hash)
    catalog = SessionCatalog(tmp_path)

    assert catalog.compatibility(reader.manifest)
    assert catalog.reader(reader.manifest.session_id).manifest == reader.manifest
    assert replay_session(reader).statistics.total_frames == 3
    result = InvestigationService(catalog).investigate(reader.manifest.session_id)
    assert result.session.calibration_id is None
    assert len(result.raw_frames) == 3


def test_recorder_rejects_backward_time_and_retains_incomplete_artifact(tmp_path: Path) -> None:
    recorder = SessionRecorder(tmp_path, session_id=SESSION_ID, created_at_utc=CREATED)
    recorder.record(RawCanFrame(0x500, b"\x01", 10))
    with pytest.raises(SessionRecordingError, match="precedes"):
        recorder.record(RawCanFrame(0x500, b"\x02", 9))
    manifest = recorder.abort("decode failure")

    assert manifest.status is SessionStatus.INCOMPLETE
    assert manifest.failure_reason == "decode failure"
    assert recorder.artifact_path.suffix == ".partial"
    assert not (tmp_path / f"{SESSION_ID}.tuneros").exists()
    with pytest.raises(SessionIntegrityError, match="not complete"):
        SessionReader(recorder.artifact_path)


def test_failed_atomic_publication_remains_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = SessionRecorder(tmp_path, session_id=SESSION_ID, created_at_utc=CREATED)
    recorder.record(_frames()[0])
    real_replace = os.replace

    def fail_final_directory_publish(source, destination) -> None:
        if Path(destination).suffix == ".tuneros":
            raise OSError("publish unavailable")
        real_replace(source, destination)

    monkeypatch.setattr("tuneros.session.recorder.os.replace", fail_final_directory_publish)
    with pytest.raises(SessionRecordingError, match="publishing"):
        recorder.complete()

    assert recorder.manifest.status is SessionStatus.INCOMPLETE
    assert recorder.artifact_path.suffix == ".partial"
    assert not tuple(tmp_path.glob("*.tuneros"))
    stored = json.loads((recorder.artifact_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert stored["status"] == "incomplete"
    with pytest.raises(SessionIntegrityError, match="not complete"):
        SessionReader(recorder.artifact_path)


@pytest.mark.parametrize(
    "header,error,match",
    [
        (b"FAIL\x01\x00\x00\x00", SessionFormatError, "magic"),
        (b"TNSR\x02\x00\x00\x00", SessionVersionError, "does not match"),
        (b"TNSR\x03\x00\x00\x00", SessionVersionError, "version 3"),
    ],
)
def test_reader_rejects_invalid_header(
    tmp_path: Path, header: bytes, error: type[Exception], match: str
) -> None:
    reader = _record(tmp_path)
    path = reader.artifact_path / FRAMES_FILENAME
    value = path.read_bytes()
    path.write_bytes(header + value[SESSION_FILE_HEADER_SIZE:])
    _rehash(reader.artifact_path)
    with pytest.raises(error, match=match):
        SessionReader(reader.artifact_path).validate_integrity()


def test_reader_rejects_truncation_count_and_hash_mismatch(tmp_path: Path) -> None:
    reader = _record(tmp_path)
    path = reader.artifact_path / FRAMES_FILENAME
    original = path.read_bytes()

    path.write_bytes(original[:-1])
    _rehash(reader.artifact_path)
    with pytest.raises(SessionIntegrityError, match="truncated"):
        SessionReader(reader.artifact_path).validate_integrity()

    path.write_bytes(original)
    _rewrite_manifest(reader.artifact_path, frame_count=2)
    with pytest.raises(SessionIntegrityError, match="file count 3"):
        SessionReader(reader.artifact_path).validate_integrity()

    _rewrite_manifest(reader.artifact_path, frame_count=4)
    with pytest.raises(SessionIntegrityError, match="file count 3"):
        SessionReader(reader.artifact_path).validate_integrity()

    _rewrite_manifest(reader.artifact_path, frame_count=3, frames_sha256="0" * 64)
    with pytest.raises(SessionIntegrityError, match="SHA-256"):
        SessionReader(reader.artifact_path).validate_integrity()

    _rewrite_manifest(
        reader.artifact_path,
        frames_sha256=hashlib.sha256(original).hexdigest(),
        first_timestamp_microseconds=1,
        duration_microseconds=19_999,
    )
    with pytest.raises(SessionIntegrityError, match="first timestamp"):
        SessionReader(reader.artifact_path).validate_integrity()


@pytest.mark.parametrize(
    "offset,value,match",
    [
        (SESSION_FILE_HEADER_SIZE + 8, b"\x08\x00", "arbitration ID"),
        (SESSION_FILE_HEADER_SIZE + 10, b"\x09", "DLC 9"),
    ],
)
def test_reader_rejects_invalid_raw_record_fields(
    tmp_path: Path, offset: int, value: bytes, match: str
) -> None:
    reader = _record(tmp_path)
    path = reader.artifact_path / FRAMES_FILENAME
    data = bytearray(path.read_bytes())
    data[offset : offset + len(value)] = value
    path.write_bytes(data)
    _rehash(reader.artifact_path)
    with pytest.raises(SessionFormatError, match=match):
        SessionReader(reader.artifact_path).validate_integrity()


def test_reader_rejects_nonmonotonic_timestamps_and_is_lazy(tmp_path: Path) -> None:
    reader = _record(tmp_path)
    iterator = reader.frames()
    path = reader.artifact_path / FRAMES_FILENAME
    data = bytearray(path.read_bytes())
    third_timestamp = SESSION_FILE_HEADER_SIZE + 2 * RAW_CAN_RECORD_SIZE
    data[third_timestamp : third_timestamp + 8] = (0).to_bytes(8, "big")
    path.write_bytes(data)
    _rehash(reader.artifact_path)

    assert next(iterator) == _frames()[0]
    assert next(iterator) == _frames()[1]
    assert next(iterator).timestamp_microseconds == 0

    data[third_timestamp : third_timestamp + 8] = (1).to_bytes(8, "big")
    second_timestamp = SESSION_FILE_HEADER_SIZE + RAW_CAN_RECORD_SIZE
    data[second_timestamp : second_timestamp + 8] = (2).to_bytes(8, "big")
    path.write_bytes(data)
    _rehash(reader.artifact_path)
    with pytest.raises(SessionIntegrityError, match="nondecreasing"):
        SessionReader(reader.artifact_path).validate_integrity()


def test_dbc_mismatch_fails_by_default(tmp_path: Path) -> None:
    reader = _record(tmp_path, dbc_sha256="0" * 64)
    with pytest.raises(SessionDbcMismatchError, match="DBC SHA-256"):
        SessionReader(reader.artifact_path, expected_dbc_sha256=authoritative_dbc_sha256())
    with pytest.raises(SessionDbcMismatchError):
        replay_session(reader)


def test_replay_uses_existing_decoder_and_is_exactly_deterministic(tmp_path: Path) -> None:
    reader = _record(tmp_path)
    first = replay_session(reader)
    second = replay_session(SessionReader(reader.artifact_path))

    assert isinstance(TunerOsDbcDecoder().decode(_frames()[0]).signals["EngineSpeedRpm"], float)
    assert first.snapshot == second.snapshot
    assert first.statistics == second.statistics
    assert first.engine.history(first.engine.catalog.find_unique_signal("EngineSpeedRpm")) == (
        second.engine.history(second.engine.catalog.find_unique_signal("EngineSpeedRpm"))
    )


def test_catalog_lists_only_complete_sessions_and_resists_path_traversal(tmp_path: Path) -> None:
    reader = _record(tmp_path)
    incomplete = SessionRecorder(tmp_path, created_at_utc=CREATED)
    incomplete.abort("test")
    catalog = SessionCatalog(tmp_path)

    assert catalog.list() == (reader.manifest,)
    assert catalog.reader(str(SESSION_ID)).manifest == reader.manifest
    with pytest.raises(KeyError):
        catalog.reader("../manifest.json")
    with pytest.raises(KeyError):
        catalog.reader("{" + str(SESSION_ID) + "}")


def test_catalog_rejects_manifest_id_that_differs_from_directory(tmp_path: Path) -> None:
    reader = _record(tmp_path)
    different_id = "87654321-4321-4678-9234-567812345678"
    renamed = tmp_path / f"{different_id}.tuneros"
    reader.artifact_path.rename(renamed)
    catalog = SessionCatalog(tmp_path)

    with pytest.raises(SessionIntegrityError, match="does not match"):
        catalog.reader(different_id)
    with pytest.raises(SessionIntegrityError, match="does not match"):
        catalog.list()
