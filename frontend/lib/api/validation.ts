import type {
  InitialSnapshotEvent,
  MessageFrameCount,
  ServiceStateEvent,
  SignalDefinition,
  SignalFreshness,
  SignalHistoryResponse,
  SignalKey,
  SignalResponse,
  SignalSample,
  TelemetryServiceState,
  TelemetrySnapshot,
  TelemetryStatistics,
  TelemetryStatus,
  TelemetryUpdateEvent,
  TelemetryWebSocketEvent,
} from "./types";

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNullableInteger(value: unknown): value is number | null {
  return value === null || isInteger(value);
}

function isInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value);
}

function isFreshness(value: unknown): value is SignalFreshness {
  return value === "fresh" || value === "stale";
}

function isServiceState(value: unknown): value is TelemetryServiceState {
  return ["stopped", "connecting", "running", "completed", "failed"].includes(
    String(value),
  );
}

function isSignalKey(value: unknown): value is SignalKey {
  return (
    isRecord(value) &&
    typeof value.message_name === "string" &&
    typeof value.signal_name === "string"
  );
}

function isSignalDefinition(value: unknown): value is SignalDefinition {
  return (
    isRecord(value) &&
    isSignalKey(value.key) &&
    typeof value.signal_name === "string" &&
    typeof value.message_name === "string" &&
    isInteger(value.arbitration_id) &&
    typeof value.arbitration_id_hex === "string" &&
    typeof value.source_ecu === "string" &&
    typeof value.unit === "string" &&
    isInteger(value.expected_period_microseconds)
  );
}

function isSignalSample(value: unknown): value is SignalSample {
  return (
    isRecord(value) &&
    isSignalKey(value.key) &&
    (typeof value.value === "number" || typeof value.value === "boolean") &&
    isInteger(value.timestamp_microseconds) &&
    isInteger(value.frame_sequence) &&
    isInteger(value.arbitration_id) &&
    typeof value.arbitration_id_hex === "string" &&
    typeof value.message_name === "string" &&
    typeof value.source_ecu === "string" &&
    typeof value.unit === "string" &&
    (value.freshness === null || isFreshness(value.freshness))
  );
}

function isMessageFrameCount(value: unknown): value is MessageFrameCount {
  return (
    isRecord(value) &&
    isInteger(value.arbitration_id) &&
    typeof value.arbitration_id_hex === "string" &&
    typeof value.message_name === "string" &&
    isInteger(value.frames)
  );
}

function isStatistics(value: unknown): value is TelemetryStatistics {
  return (
    isRecord(value) &&
    isInteger(value.total_frames) &&
    isInteger(value.total_signal_updates) &&
    isNullableInteger(value.latest_timestamp_microseconds) &&
    isNullableInteger(value.last_frame_sequence) &&
    Array.isArray(value.frames_by_message) &&
    value.frames_by_message.every(isMessageFrameCount)
  );
}

export function isTelemetrySnapshot(value: unknown): value is TelemetrySnapshot {
  return (
    isRecord(value) &&
    isNullableInteger(value.observation_timestamp_microseconds) &&
    isNullableInteger(value.last_frame_sequence) &&
    Array.isArray(value.signals) &&
    value.signals.every(isSignalSample) &&
    isStatistics(value.statistics)
  );
}

export function parseStatus(value: unknown): TelemetryStatus {
  if (
    !isRecord(value) ||
    !isServiceState(value.service_state) ||
    typeof value.gateway_connected !== "boolean" ||
    (value.last_error !== null && typeof value.last_error !== "string") ||
    !isNullableInteger(value.latest_timestamp_microseconds) ||
    !isInteger(value.total_frames) ||
    !isInteger(value.total_signal_updates)
  ) {
    throw new Error("Backend returned an invalid telemetry status response");
  }
  return {
    service_state: value.service_state,
    gateway_connected: value.gateway_connected,
    last_error: value.last_error,
    latest_timestamp_microseconds: value.latest_timestamp_microseconds,
    total_frames: value.total_frames,
    total_signal_updates: value.total_signal_updates,
  };
}

export function parseCatalog(value: unknown): SignalDefinition[] {
  if (!Array.isArray(value) || !value.every(isSignalDefinition)) {
    throw new Error("Backend returned an invalid signal catalog response");
  }
  return value;
}

export function parseSnapshot(value: unknown): TelemetrySnapshot {
  if (!isTelemetrySnapshot(value)) {
    throw new Error("Backend returned an invalid telemetry snapshot response");
  }
  return value;
}

export function parseSignalResponse(value: unknown): SignalResponse {
  if (
    !isRecord(value) ||
    !isSignalDefinition(value.definition) ||
    (value.sample !== null && !isSignalSample(value.sample)) ||
    (value.freshness !== null && !isFreshness(value.freshness))
  ) {
    throw new Error("Backend returned an invalid signal response");
  }
  return {
    definition: value.definition,
    sample: value.sample,
    freshness: value.freshness,
  };
}

export function parseSignalHistoryResponse(value: unknown): SignalHistoryResponse {
  if (
    !isRecord(value) ||
    !isSignalDefinition(value.definition) ||
    !Array.isArray(value.samples) ||
    !value.samples.every(isSignalSample)
  ) {
    throw new Error("Backend returned an invalid signal history response");
  }
  return { definition: value.definition, samples: value.samples };
}

export function parseWebSocketEvent(value: unknown): TelemetryWebSocketEvent {
  if (!isRecord(value) || typeof value.type !== "string") {
    throw new Error("Telemetry WebSocket sent an invalid event envelope");
  }
  if (value.type === "initial_snapshot" && isTelemetrySnapshot(value.snapshot)) {
    const event: InitialSnapshotEvent = { type: "initial_snapshot", snapshot: value.snapshot };
    return event;
  }
  if (
    value.type === "telemetry_update" &&
    isInteger(value.timestamp_microseconds) &&
    isInteger(value.frame_sequence) &&
    isInteger(value.arbitration_id) &&
    typeof value.arbitration_id_hex === "string" &&
    typeof value.message_name === "string" &&
    typeof value.source_ecu === "string" &&
    Array.isArray(value.signals) &&
    value.signals.every(isSignalSample)
  ) {
    const event: TelemetryUpdateEvent = {
      type: "telemetry_update",
      timestamp_microseconds: value.timestamp_microseconds,
      frame_sequence: value.frame_sequence,
      arbitration_id: value.arbitration_id,
      arbitration_id_hex: value.arbitration_id_hex,
      message_name: value.message_name,
      source_ecu: value.source_ecu,
      signals: value.signals,
    };
    return event;
  }
  if (
    value.type === "service_state" &&
    isServiceState(value.state) &&
    (value.error === null || typeof value.error === "string")
  ) {
    const event: ServiceStateEvent = {
      type: "service_state",
      state: value.state,
      error: value.error,
    };
    return event;
  }
  throw new Error(`Telemetry WebSocket sent an invalid ${value.type} event`);
}
