"""Synchronous deterministic telemetry aggregation engine."""

from collections import deque
from collections.abc import Iterable, Mapping
from types import MappingProxyType

from tuneros.can import DecodedCanFrame
from tuneros.telemetry.catalog import SignalCatalog
from tuneros.telemetry.models import (
    OutOfOrderTelemetryError,
    SignalFreshness,
    SignalKey,
    SignalSample,
    TelemetrySchemaError,
    TelemetrySnapshot,
    TelemetryStatistics,
)

DEFAULT_HISTORY_CAPACITY = 256
FRESHNESS_PERIOD_MULTIPLIER = 2


class TelemetryEngine:
    """Latest state and bounded histories built exclusively from decoded CAN frames."""

    def __init__(self, catalog: SignalCatalog, history_capacity: int = DEFAULT_HISTORY_CAPACITY):
        if isinstance(history_capacity, bool) or not isinstance(history_capacity, int):
            raise TypeError("history_capacity must be an integer")
        if history_capacity <= 0:
            raise ValueError("history_capacity must be positive")
        self._catalog = catalog
        self._history_capacity = history_capacity
        self.reset()

    @property
    def catalog(self) -> SignalCatalog:
        return self._catalog

    @property
    def history_capacity(self) -> int:
        return self._history_capacity

    def ingest(self, frame: DecodedCanFrame) -> tuple[SignalSample, ...]:
        if (
            self._latest_timestamp_microseconds is not None
            and frame.timestamp_microseconds < self._latest_timestamp_microseconds
        ):
            raise OutOfOrderTelemetryError(
                f"frame {frame.message_name} 0x{frame.arbitration_id:03X} timestamp "
                f"{frame.timestamp_microseconds} precedes latest timestamp "
                f"{self._latest_timestamp_microseconds}"
            )

        definitions = self._catalog.definitions_for_frame(frame)
        frame_sequence = self._next_frame_sequence
        samples = tuple(
            SignalSample(
                key=definition.key,
                value=value,
                timestamp_microseconds=frame.timestamp_microseconds,
                frame_sequence=frame_sequence,
                arbitration_id=frame.arbitration_id,
                message_name=frame.message_name,
                source_ecu=definition.source_ecu,
                unit=definition.unit,
            )
            for definition, value in zip(definitions, frame.signals.values(), strict=True)
        )
        if any(type(sample.value) not in (bool, int, float) for sample in samples):
            raise TelemetrySchemaError("decoded telemetry values must be float, int, or bool")

        # Mutation begins only after the complete decoded frame has been validated and materialized.
        for sample in samples:
            history = self._histories.setdefault(sample.key, deque(maxlen=self._history_capacity))
            history.append(sample)
            self._latest[sample.key] = sample
        self._total_frames += 1
        self._total_signal_updates += len(samples)
        self._frames_by_arbitration_id[frame.arbitration_id] = (
            self._frames_by_arbitration_id.get(frame.arbitration_id, 0) + 1
        )
        self._latest_timestamp_microseconds = frame.timestamp_microseconds
        self._last_frame_sequence = frame_sequence
        self._next_frame_sequence += 1
        return samples

    def latest(self, key: SignalKey) -> SignalSample | None:
        self._catalog.require(key)
        return self._latest.get(key)

    def latest_all(self) -> Mapping[SignalKey, SignalSample]:
        return MappingProxyType(dict(self._latest))

    def history(self, key: SignalKey) -> tuple[SignalSample, ...]:
        self._catalog.require(key)
        return tuple(self._histories.get(key, ()))

    def freshness(
        self, key: SignalKey, observation_timestamp_microseconds: int | None = None
    ) -> SignalFreshness | None:
        definition = self._catalog.require(key)
        sample = self._latest.get(key)
        if sample is None:
            return None
        observation_timestamp = (
            self._latest_timestamp_microseconds
            if observation_timestamp_microseconds is None
            else observation_timestamp_microseconds
        )
        if observation_timestamp is None or observation_timestamp < sample.timestamp_microseconds:
            raise ValueError("freshness observation timestamp cannot precede the signal sample")
        age = observation_timestamp - sample.timestamp_microseconds
        threshold = definition.expected_period_microseconds * FRESHNESS_PERIOD_MULTIPLIER
        return SignalFreshness.FRESH if age <= threshold else SignalFreshness.STALE

    def statistics(self) -> TelemetryStatistics:
        return TelemetryStatistics(
            total_frames=self._total_frames,
            total_signal_updates=self._total_signal_updates,
            latest_timestamp_microseconds=self._latest_timestamp_microseconds,
            last_frame_sequence=self._last_frame_sequence,
            frames_by_arbitration_id=self._frames_by_arbitration_id,
        )

    def snapshot(self, keys: Iterable[SignalKey] | None = None) -> TelemetrySnapshot:
        if keys is None:
            samples = dict(self._latest)
        else:
            samples = {}
            for key in keys:
                self._catalog.require(key)
                sample = self._latest.get(key)
                if sample is not None:
                    samples[key] = sample
        statuses = {key: self.freshness(key) for key in samples}
        return TelemetrySnapshot(
            observation_timestamp_microseconds=self._latest_timestamp_microseconds,
            last_frame_sequence=self._last_frame_sequence,
            samples=samples,
            freshness=statuses,
            statistics=self.statistics(),
        )

    def reset(self) -> None:
        self._latest: dict[SignalKey, SignalSample] = {}
        self._histories: dict[SignalKey, deque[SignalSample]] = {}
        self._next_frame_sequence = 0
        self._total_frames = 0
        self._total_signal_updates = 0
        self._latest_timestamp_microseconds: int | None = None
        self._last_frame_sequence: int | None = None
        self._frames_by_arbitration_id: dict[int, int] = {}
