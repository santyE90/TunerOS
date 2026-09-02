"""DBC-backed decoder for the synthetic TunerOS CAN network."""

from importlib.resources import as_file, files

import canmatrix
import canmatrix.formats

from tuneros.can.metadata import CanDatabaseMetadata, CanMessageMetadata, CanSignalMetadata
from tuneros.can.models import DecodedCanFrame, RawCanFrame, SignalValue

_DBC_RESOURCE = files("tuneros.can").joinpath("dbc", "tuneros_simulation.dbc")


class CanDecodeError(ValueError):
    """Base error for a raw frame that cannot be decoded under the TunerOS DBC contract."""


class UnknownCanFrameError(CanDecodeError):
    """Raised when a valid raw frame ID is absent from the authoritative DBC."""


class MalformedCanFrameError(CanDecodeError):
    """Raised when a known frame violates its fixed payload contract."""


class TunerOsDbcDecoder:
    """Synchronous raw-frame decoder backed only by the packaged authoritative DBC."""

    def __init__(self) -> None:
        with as_file(_DBC_RESOURCE) as dbc_path:
            databases = canmatrix.formats.loadp(str(dbc_path))
        if len(databases) != 1:
            raise RuntimeError("authoritative TunerOS DBC must contain exactly one CAN database")
        self._database = next(iter(databases.values()))
        self._frames_by_id = {frame.arbitration_id.id: frame for frame in self._database.frames}
        self._database_metadata = CanDatabaseMetadata(
            messages=tuple(
                CanMessageMetadata(
                    arbitration_id=frame.arbitration_id.id,
                    message_name=frame.name,
                    transmitter=self._single_transmitter(frame),
                    cycle_time_microseconds=self._cycle_time_microseconds(frame),
                    signals=tuple(
                        CanSignalMetadata(signal_name=signal.name, unit=signal.unit or "")
                        for signal in frame.signals
                    ),
                )
                for frame in self._database.frames
            )
        )

    @staticmethod
    def _single_transmitter(frame) -> str:
        if len(frame.transmitters) != 1:
            raise RuntimeError(
                f"{frame.name} must define exactly one authoritative synthetic transmitter"
            )
        return frame.transmitters[0]

    @staticmethod
    def _cycle_time_microseconds(frame) -> int:
        cycle_time_milliseconds = frame.cycle_time
        if cycle_time_milliseconds <= 0:
            raise RuntimeError(f"{frame.name} must define a positive DBC cycle time")
        return cycle_time_milliseconds * 1_000

    @property
    def database_metadata(self) -> CanDatabaseMetadata:
        return self._database_metadata

    @property
    def supported_arbitration_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._frames_by_id))

    def supports(self, arbitration_id: int) -> bool:
        return arbitration_id in self._frames_by_id

    def message_name(self, arbitration_id: int) -> str:
        try:
            return self._frames_by_id[arbitration_id].name
        except KeyError as error:
            raise UnknownCanFrameError(
                f"CAN arbitration ID 0x{arbitration_id:03X} is not defined by the TunerOS DBC"
            ) from error

    def decode(self, frame: RawCanFrame) -> DecodedCanFrame:
        try:
            message = self._frames_by_id[frame.arbitration_id]
        except KeyError as error:
            raise UnknownCanFrameError(
                f"CAN arbitration ID 0x{frame.arbitration_id:03X} is not defined by the TunerOS DBC"
            ) from error

        if frame.payload_length != message.size:
            raise MalformedCanFrameError(
                f"{message.name} requires DLC {message.size}, got {frame.payload_length}"
            )

        try:
            decoded = message.decode(frame.payload)
        except canmatrix.DecodingFrameLength as error:
            raise MalformedCanFrameError(f"could not decode {message.name}") from error

        signals: dict[str, SignalValue] = {
            name: bool(value.raw_value) if name == "EngineRunning" else float(value.phys_value)
            for name, value in decoded.items()
        }
        return DecodedCanFrame(
            arbitration_id=frame.arbitration_id,
            message_name=message.name,
            timestamp_microseconds=frame.timestamp_microseconds,
            signals=signals,
        )
