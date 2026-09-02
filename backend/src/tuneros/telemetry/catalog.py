"""Telemetry signal identity and provenance derived from CAN database metadata."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from tuneros.can import CanDatabaseMetadata, CanMessageMetadata, DecodedCanFrame
from tuneros.telemetry.models import SignalKey, TelemetrySchemaError


@dataclass(frozen=True, slots=True)
class SignalDefinition:
    key: SignalKey
    arbitration_id: int
    message_name: str
    source_ecu: str
    unit: str
    expected_period_microseconds: int


class SignalCatalog:
    """Immutable telemetry view of authoritative DBC signal metadata."""

    def __init__(self, database_metadata: CanDatabaseMetadata) -> None:
        definitions: list[SignalDefinition] = []
        messages_by_id: dict[int, CanMessageMetadata] = {}
        definitions_by_key: dict[SignalKey, SignalDefinition] = {}
        keys_by_signal_name: dict[str, list[SignalKey]] = {}

        for message in database_metadata.messages:
            if message.arbitration_id in messages_by_id:
                raise TelemetrySchemaError(
                    f"duplicate CAN message ID 0x{message.arbitration_id:03X} in metadata"
                )
            messages_by_id[message.arbitration_id] = message
            for signal in message.signals:
                key = SignalKey(message.message_name, signal.signal_name)
                if key in definitions_by_key:
                    raise TelemetrySchemaError(f"duplicate telemetry signal key {key}")
                definition = SignalDefinition(
                    key=key,
                    arbitration_id=message.arbitration_id,
                    message_name=message.message_name,
                    source_ecu=message.transmitter,
                    unit=signal.unit,
                    expected_period_microseconds=message.cycle_time_microseconds,
                )
                definitions.append(definition)
                definitions_by_key[key] = definition
                keys_by_signal_name.setdefault(signal.signal_name, []).append(key)

        self._definitions = tuple(definitions)
        self._messages_by_id: Mapping[int, CanMessageMetadata] = MappingProxyType(messages_by_id)
        self._definitions_by_key: Mapping[SignalKey, SignalDefinition] = MappingProxyType(
            definitions_by_key
        )
        self._keys_by_signal_name = {
            name: tuple(keys) for name, keys in keys_by_signal_name.items()
        }

    @property
    def definitions(self) -> tuple[SignalDefinition, ...]:
        return self._definitions

    def get(self, key: SignalKey) -> SignalDefinition | None:
        return self._definitions_by_key.get(key)

    def require(self, key: SignalKey) -> SignalDefinition:
        definition = self.get(key)
        if definition is None:
            raise TelemetrySchemaError(f"signal is absent from authoritative catalog: {key}")
        return definition

    def find_unique_signal(self, signal_name: str) -> SignalKey | None:
        keys = self._keys_by_signal_name.get(signal_name, ())
        if not keys:
            return None
        if len(keys) > 1:
            raise TelemetrySchemaError(
                f"signal name {signal_name!r} is ambiguous across {len(keys)} messages"
            )
        return keys[0]

    def definitions_for_frame(self, frame: DecodedCanFrame) -> tuple[SignalDefinition, ...]:
        message = self._messages_by_id.get(frame.arbitration_id)
        if message is None:
            raise TelemetrySchemaError(
                f"decoded frame uses unknown arbitration ID 0x{frame.arbitration_id:03X}"
            )
        if frame.message_name != message.message_name:
            raise TelemetrySchemaError(
                f"decoded frame ID 0x{frame.arbitration_id:03X} is {message.message_name}, "
                f"not {frame.message_name}"
            )

        definitions: list[SignalDefinition] = []
        for signal_name in frame.signals:
            key = SignalKey(frame.message_name, signal_name)
            definition = self._definitions_by_key.get(key)
            if definition is None:
                raise TelemetrySchemaError(
                    f"signal {signal_name!r} is not defined for {frame.message_name}"
                )
            definitions.append(definition)
        return tuple(definitions)
