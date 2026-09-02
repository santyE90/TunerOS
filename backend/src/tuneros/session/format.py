"""On-disk byte and JSON helpers for TunerOS session format version 1."""

import json
import os
import struct
from pathlib import Path

from tuneros.session.errors import SessionFormatError, SessionVersionError
from tuneros.session.models import SESSION_FORMAT_VERSION, SessionManifest

SESSION_FILE_MAGIC = b"TNSR"
SESSION_FILE_HEADER_SIZE = 8
SESSION_FILE_HEADER = struct.Struct("!4sB3s")
MANIFEST_FILENAME = "manifest.json"
FRAMES_FILENAME = "frames.bin"


def encode_session_header() -> bytes:
    return SESSION_FILE_HEADER.pack(SESSION_FILE_MAGIC, SESSION_FORMAT_VERSION, b"\x00\x00\x00")


def decode_session_header(data: bytes) -> None:
    if len(data) != SESSION_FILE_HEADER_SIZE:
        raise SessionFormatError(
            f"session frame header requires {SESSION_FILE_HEADER_SIZE} bytes, got {len(data)}"
        )
    magic, version, reserved = SESSION_FILE_HEADER.unpack(data)
    if magic != SESSION_FILE_MAGIC:
        raise SessionFormatError(f"invalid session frame magic {magic!r}")
    if version != SESSION_FORMAT_VERSION:
        raise SessionVersionError(f"unsupported session frame version {version}")
    if reserved != b"\x00\x00\x00":
        raise SessionFormatError("session frame header reserved bytes must be zero")


def write_manifest_atomic(path: Path, manifest: SessionManifest) -> None:
    temporary = path.with_suffix(".json.tmp")
    data = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_manifest(path: Path) -> SessionManifest:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SessionFormatError("session manifest is missing") from error
    except (OSError, json.JSONDecodeError) as error:
        raise SessionFormatError("session manifest is not valid JSON") from error
    return SessionManifest.from_dict(value)
