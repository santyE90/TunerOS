"""Filesystem catalog for immutable complete TunerOS session artifacts."""

from pathlib import Path
from uuid import UUID

from tuneros.can import is_supported_dbc_sha256
from tuneros.session.errors import SessionDbcMismatchError, SessionIntegrityError
from tuneros.session.models import SessionManifest
from tuneros.session.reader import SessionReader
from tuneros.session.recorder import DEFAULT_SESSION_ROOT


class SessionCatalog:
    def __init__(self, session_root: Path = DEFAULT_SESSION_ROOT) -> None:
        self._session_root = Path(session_root)

    @property
    def session_root(self) -> Path:
        return self._session_root

    def list(self) -> tuple[SessionManifest, ...]:
        if not self._session_root.exists():
            return ()
        manifests = []
        for artifact in sorted(self._session_root.glob("*.tuneros")):
            try:
                contained_artifact = self._contained_artifact(artifact)
                artifact_id = self._canonical_id(artifact.stem)
            except KeyError:
                continue
            reader = SessionReader(contained_artifact)
            reader.validate_integrity()
            self._validate_manifest_id(reader, artifact_id)
            manifests.append(reader.manifest)
        return tuple(
            sorted(manifests, key=lambda item: (item.created_at_utc, item.session_id), reverse=True)
        )

    def reader(self, session_id: str, *, require_compatible_dbc: bool = True) -> SessionReader:
        canonical = self._canonical_id(session_id)
        artifact = self._contained_artifact(self._session_root / f"{canonical}.tuneros")
        if not artifact.is_dir():
            raise KeyError(f"unknown session {canonical}")
        reader = SessionReader(artifact)
        reader.validate_integrity()
        if require_compatible_dbc and not self.compatibility(reader.manifest):
            raise SessionDbcMismatchError(
                "recorded DBC SHA-256 is not compatible with the installed authoritative DBC"
            )
        self._validate_manifest_id(reader, canonical)
        return reader

    def compatibility(self, manifest: SessionManifest) -> bool:
        return is_supported_dbc_sha256(manifest.dbc_sha256)

    def _contained_artifact(self, artifact: Path) -> Path:
        root = self._session_root.resolve()
        resolved = artifact.resolve()
        if resolved.parent != root:
            raise KeyError("session artifact must remain inside the configured session root")
        return resolved

    @staticmethod
    def _canonical_id(session_id: str) -> str:
        try:
            identifier = UUID(session_id)
        except (ValueError, AttributeError) as error:
            raise KeyError("invalid session ID") from error
        canonical = str(identifier)
        if canonical != session_id:
            raise KeyError("session ID must use canonical UUID form")
        return canonical

    @staticmethod
    def _validate_manifest_id(reader: SessionReader, artifact_id: str) -> None:
        if reader.manifest.session_id != artifact_id:
            raise SessionIntegrityError("manifest session ID does not match artifact directory")
