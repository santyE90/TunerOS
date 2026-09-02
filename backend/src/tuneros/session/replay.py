"""Deterministic unpaced replay through the existing DBC and telemetry engine."""

from dataclasses import dataclass

from tuneros.can import CanExplorer, TunerOsDbcDecoder, authoritative_dbc_sha256
from tuneros.session.reader import SessionReader
from tuneros.telemetry import DEFAULT_HISTORY_CAPACITY, SignalCatalog, TelemetryEngine
from tuneros.telemetry.models import TelemetrySnapshot, TelemetryStatistics


@dataclass(frozen=True, slots=True)
class SessionReplayResult:
    snapshot: TelemetrySnapshot
    statistics: TelemetryStatistics
    engine: TelemetryEngine
    explorer: CanExplorer


def replay_session(
    reader: SessionReader,
    *,
    decoder: TunerOsDbcDecoder | None = None,
    explorer: CanExplorer | None = None,
    history_capacity: int = DEFAULT_HISTORY_CAPACITY,
) -> SessionReplayResult:
    if reader.manifest.dbc_sha256 != authoritative_dbc_sha256():
        from tuneros.session.errors import SessionDbcMismatchError

        raise SessionDbcMismatchError(
            "recorded DBC SHA-256 does not match the installed authoritative DBC"
        )
    reader.validate_integrity()
    active_decoder = decoder or TunerOsDbcDecoder()
    active_explorer = explorer or CanExplorer(active_decoder)
    active_explorer.reset()
    engine = TelemetryEngine(SignalCatalog(active_decoder.database_metadata), history_capacity)
    for raw_frame in reader.frames():
        active_explorer.ingest(raw_frame)
        engine.ingest(active_decoder.decode(raw_frame))
    return SessionReplayResult(engine.snapshot(), engine.statistics(), engine, active_explorer)
