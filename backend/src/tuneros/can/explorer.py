"""Bounded raw-CAN inspection state annotated by the authoritative DBC."""

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from tuneros.can.decoder import CanDecodeError, TunerOsDbcDecoder, UnknownCanFrameError
from tuneros.can.metadata import CanMessageMetadata
from tuneros.can.models import RawCanFrame, SignalValue

DEFAULT_CAN_EXPLORER_CAPACITY = 4_096


class CanDecodeStatus(StrEnum):
    DECODED = "decoded"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class CanExplorerSignal:
    signal_name: str
    value: SignalValue
    unit: str


@dataclass(frozen=True, slots=True)
class CanExplorerFrame:
    sequence: int
    raw_frame: RawCanFrame
    message_name: str | None
    source_ecu: str | None
    expected_period_microseconds: int | None
    decode_status: CanDecodeStatus
    decode_error: str | None
    decoded_signals: tuple[CanExplorerSignal, ...]


@dataclass(frozen=True, slots=True)
class CanMessageStatistics:
    arbitration_id: int
    message_name: str | None
    source_ecu: str | None
    retained_frame_count: int
    total_frame_count: int
    first_timestamp_microseconds: int
    latest_timestamp_microseconds: int
    expected_period_microseconds: int | None
    observed_average_period_microseconds: float | None
    observed_frequency_hz: float | None
    latest_dlc: int


@dataclass(frozen=True, slots=True)
class CanExplorerStatistics:
    retained_frame_count: int
    total_frame_count: int
    unique_id_count: int
    oldest_retained_timestamp_microseconds: int | None
    newest_retained_timestamp_microseconds: int | None
    last_sequence: int | None


@dataclass(frozen=True, slots=True)
class CanExplorerSnapshot:
    frames: tuple[CanExplorerFrame, ...]
    statistics: CanExplorerStatistics
    messages: tuple[CanMessageStatistics, ...]


@dataclass(slots=True)
class _MutableMessageStatistics:
    arbitration_id: int
    metadata: CanMessageMetadata | None
    retained_frame_count: int
    total_frame_count: int
    first_timestamp_microseconds: int
    latest_timestamp_microseconds: int
    latest_dlc: int


class CanExplorer:
    """Observe raw frames in arrival order without owning their source or telemetry state."""

    def __init__(
        self,
        decoder: TunerOsDbcDecoder | None = None,
        capacity: int = DEFAULT_CAN_EXPLORER_CAPACITY,
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError("CAN explorer capacity must be an integer")
        if capacity <= 0:
            raise ValueError("CAN explorer capacity must be positive")
        self._decoder = decoder or TunerOsDbcDecoder()
        self._metadata_by_id = {
            message.arbitration_id: message for message in self._decoder.database_metadata.messages
        }
        self._capacity = capacity
        self._frames: deque[CanExplorerFrame] = deque(maxlen=capacity)
        self._messages: dict[int, _MutableMessageStatistics] = {}
        self._next_sequence = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def ingest(self, raw_frame: RawCanFrame) -> CanExplorerFrame:
        metadata = self._metadata_by_id.get(raw_frame.arbitration_id)
        decoded_signals: tuple[CanExplorerSignal, ...] = ()
        decode_error: str | None = None
        if metadata is None:
            decode_status = CanDecodeStatus.UNKNOWN
        else:
            try:
                decoded = self._decoder.decode(raw_frame)
                values = decoded.signals
                decoded_signals = tuple(
                    CanExplorerSignal(signal.signal_name, values[signal.signal_name], signal.unit)
                    for signal in metadata.signals
                )
                decode_status = CanDecodeStatus.DECODED
            except UnknownCanFrameError:  # pragma: no cover - metadata/decoder share one DBC
                metadata = None
                decode_status = CanDecodeStatus.UNKNOWN
            except CanDecodeError as error:
                decode_status = CanDecodeStatus.ERROR
                decode_error = str(error)

        frame = CanExplorerFrame(
            sequence=self._next_sequence,
            raw_frame=raw_frame,
            message_name=None if metadata is None else metadata.message_name,
            source_ecu=None if metadata is None else metadata.transmitter,
            expected_period_microseconds=(
                None if metadata is None else metadata.cycle_time_microseconds
            ),
            decode_status=decode_status,
            decode_error=decode_error,
            decoded_signals=decoded_signals,
        )
        self._next_sequence += 1
        if len(self._frames) == self._capacity:
            evicted = self._frames[0]
            self._messages[evicted.raw_frame.arbitration_id].retained_frame_count -= 1
        self._frames.append(frame)
        self._update_message(raw_frame, metadata)
        return frame

    def frames(
        self,
        *,
        limit: int | None = None,
        arbitration_id: int | None = None,
        message_name: str | None = None,
        source_ecu: str | None = None,
    ) -> tuple[CanExplorerFrame, ...]:
        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise TypeError("CAN frame limit must be an integer")
            if limit <= 0:
                raise ValueError("CAN frame limit must be positive")
        selected: Iterable[CanExplorerFrame] = self._frames
        if arbitration_id is not None:
            selected = (
                item for item in selected if item.raw_frame.arbitration_id == arbitration_id
            )
        if message_name is not None:
            selected = (item for item in selected if item.message_name == message_name)
        if source_ecu is not None:
            selected = (item for item in selected if item.source_ecu == source_ecu)
        result = tuple(selected)
        return result if limit is None else result[-limit:]

    def frame(self, sequence: int) -> CanExplorerFrame | None:
        return next((item for item in self._frames if item.sequence == sequence), None)

    def message_statistics(self) -> tuple[CanMessageStatistics, ...]:
        return tuple(self._freeze_message(self._messages[key]) for key in sorted(self._messages))

    def message_statistic(self, arbitration_id: int) -> CanMessageStatistics:
        return self._freeze_message(self._messages[arbitration_id])

    def statistics(self) -> CanExplorerStatistics:
        oldest = self._frames[0].raw_frame.timestamp_microseconds if self._frames else None
        newest = self._frames[-1].raw_frame.timestamp_microseconds if self._frames else None
        return CanExplorerStatistics(
            retained_frame_count=len(self._frames),
            total_frame_count=self._next_sequence,
            unique_id_count=len(self._messages),
            oldest_retained_timestamp_microseconds=oldest,
            newest_retained_timestamp_microseconds=newest,
            last_sequence=self._next_sequence - 1 if self._next_sequence else None,
        )

    def snapshot(self, *, frame_limit: int | None = None) -> CanExplorerSnapshot:
        return CanExplorerSnapshot(
            frames=self.frames(limit=frame_limit),
            statistics=self.statistics(),
            messages=self.message_statistics(),
        )

    def reset(self) -> None:
        self._frames.clear()
        self._messages.clear()
        self._next_sequence = 0

    def _update_message(self, raw_frame: RawCanFrame, metadata: CanMessageMetadata | None) -> None:
        statistics = self._messages.get(raw_frame.arbitration_id)
        if statistics is None:
            self._messages[raw_frame.arbitration_id] = _MutableMessageStatistics(
                arbitration_id=raw_frame.arbitration_id,
                metadata=metadata,
                retained_frame_count=1,
                total_frame_count=1,
                first_timestamp_microseconds=raw_frame.timestamp_microseconds,
                latest_timestamp_microseconds=raw_frame.timestamp_microseconds,
                latest_dlc=raw_frame.payload_length,
            )
            return
        statistics.retained_frame_count += 1
        statistics.total_frame_count += 1
        statistics.latest_timestamp_microseconds = raw_frame.timestamp_microseconds
        statistics.latest_dlc = raw_frame.payload_length

    @staticmethod
    def _freeze_message(statistics: _MutableMessageStatistics) -> CanMessageStatistics:
        period: float | None = None
        frequency: float | None = None
        if statistics.total_frame_count >= 2:
            period = (
                statistics.latest_timestamp_microseconds - statistics.first_timestamp_microseconds
            ) / (statistics.total_frame_count - 1)
            if period > 0:
                frequency = 1_000_000.0 / period
        metadata = statistics.metadata
        return CanMessageStatistics(
            arbitration_id=statistics.arbitration_id,
            message_name=None if metadata is None else metadata.message_name,
            source_ecu=None if metadata is None else metadata.transmitter,
            retained_frame_count=statistics.retained_frame_count,
            total_frame_count=statistics.total_frame_count,
            first_timestamp_microseconds=statistics.first_timestamp_microseconds,
            latest_timestamp_microseconds=statistics.latest_timestamp_microseconds,
            expected_period_microseconds=(
                None if metadata is None else metadata.cycle_time_microseconds
            ),
            observed_average_period_microseconds=period,
            observed_frequency_hz=frequency,
            latest_dlc=statistics.latest_dlc,
        )
