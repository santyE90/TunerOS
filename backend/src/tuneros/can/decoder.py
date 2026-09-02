"""DBC-backed decoder for the synthetic TunerOS CAN network."""

from importlib.resources import as_file, files

import canmatrix
import canmatrix.formats

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
