import type {
  CanExplorerFrame,
  CanExplorerStatistics,
  CanMessageStatistics,
  CanWebSocketEvent,
  DiagnosticEvent,
  DiagnosticFreezeFrame,
  DiagnosticSummary,
  DiagnosticTroubleCode,
  InitialSnapshotEvent,
  MessageFrameCount,
  ServiceStateEvent,
  SessionDetail,
  SessionReplayResponse,
  SessionSummary,
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
  TelemetrySource,
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

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isSessionSummary(value: unknown): value is SessionSummary {
  return (
    isRecord(value) &&
    typeof value.session_id === "string" &&
    isNullableString(value.name) &&
    typeof value.created_at_utc === "string" &&
    isNullableString(value.scenario) &&
    value.status === "complete" &&
    isInteger(value.frame_count) &&
    isInteger(value.duration_microseconds) &&
    typeof value.dbc_compatible === "boolean"
  );
}

function isSessionDetail(value: unknown): value is SessionDetail {
  return (
    isRecord(value) &&
    isSessionSummary(value) &&
    typeof value.format_name === "string" &&
    isInteger(value.format_version) &&
    typeof value.vehicle_profile_id === "string" &&
    typeof value.can_network === "string" &&
    typeof value.dbc_name === "string" &&
    typeof value.dbc_sha256 === "string" &&
    typeof value.frames_sha256 === "string" &&
    isNullableInteger(value.first_timestamp_microseconds) &&
    isNullableInteger(value.last_timestamp_microseconds)
  );
}

function isCanFrame(value: unknown): value is CanExplorerFrame {
  return (
    isRecord(value) &&
    isInteger(value.sequence) &&
    isInteger(value.timestamp_microseconds) &&
    isInteger(value.arbitration_id) &&
    typeof value.arbitration_id_hex === "string" &&
    isInteger(value.dlc) &&
    value.dlc >= 0 &&
    value.dlc <= 8 &&
    Array.isArray(value.payload) &&
    value.payload.length === value.dlc &&
    value.payload.every((byte) => isInteger(byte) && byte >= 0 && byte <= 255) &&
    typeof value.payload_hex === "string" &&
    isNullableString(value.message_name) &&
    isNullableString(value.source_ecu) &&
    isNullableInteger(value.expected_period_microseconds) &&
    ["decoded", "unknown", "error"].includes(String(value.decode_status)) &&
    isNullableString(value.decode_error) &&
    Array.isArray(value.decoded_signals) &&
    value.decoded_signals.every(
      (signal) =>
        isRecord(signal) &&
        typeof signal.signal_name === "string" &&
        (typeof signal.value === "number" || typeof signal.value === "boolean") &&
        typeof signal.unit === "string",
    )
  );
}

function isCanMessageStatistics(value: unknown): value is CanMessageStatistics {
  return (
    isRecord(value) &&
    isInteger(value.arbitration_id) &&
    typeof value.arbitration_id_hex === "string" &&
    isNullableString(value.message_name) &&
    isNullableString(value.source_ecu) &&
    isInteger(value.retained_frame_count) &&
    isInteger(value.total_frame_count) &&
    isInteger(value.first_timestamp_microseconds) &&
    isInteger(value.latest_timestamp_microseconds) &&
    isNullableInteger(value.expected_period_microseconds) &&
    (value.observed_average_period_microseconds === null ||
      typeof value.observed_average_period_microseconds === "number") &&
    (value.observed_frequency_hz === null || typeof value.observed_frequency_hz === "number") &&
    isInteger(value.latest_dlc)
  );
}

function isSource(value: unknown): value is TelemetrySource {
  return (
    isRecord(value) &&
    (value.mode === "live" || value.mode === "replay") &&
    isNullableString(value.session_id) &&
    isNullableString(value.session_name) &&
    typeof value.recording === "boolean" &&
    isInteger(value.recorded_frame_count)
  );
}

function isCanStatistics(value: unknown): value is CanExplorerStatistics {
  return (
    isRecord(value) &&
    isInteger(value.retained_frame_count) &&
    isInteger(value.total_frame_count) &&
    isInteger(value.unique_id_count) &&
    isNullableInteger(value.oldest_retained_timestamp_microseconds) &&
    isNullableInteger(value.newest_retained_timestamp_microseconds) &&
    isNullableInteger(value.last_sequence) &&
    isSource(value.source)
  );
}

function isDiagnosticStatus(value: unknown): boolean {
  return ["pending", "active", "historical", "cleared"].includes(String(value));
}

function isDiagnosticDefinition(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.code === "string" &&
    typeof value.rule_id === "string" &&
    typeof value.name === "string" &&
    typeof value.description === "string" &&
    ["info", "warning", "critical"].includes(String(value.severity)) &&
    typeof value.source_system === "string" &&
    Array.isArray(value.required_signals) &&
    value.required_signals.every(isSignalKey) &&
    isInteger(value.confirmation_duration_microseconds) &&
    isInteger(value.recovery_duration_microseconds) &&
    typeof value.activation_description === "string" &&
    typeof value.recovery_description === "string"
  );
}

function isDiagnosticTroubleCode(value: unknown): value is DiagnosticTroubleCode {
  return (
    isRecord(value) &&
    isDiagnosticDefinition(value.definition) &&
    isDiagnosticStatus(value.status) &&
    isInteger(value.first_detected_timestamp_microseconds) &&
    isNullableInteger(value.confirmed_timestamp_microseconds) &&
    isInteger(value.last_seen_timestamp_microseconds) &&
    isNullableInteger(value.resolved_timestamp_microseconds) &&
    isNullableInteger(value.cleared_timestamp_microseconds) &&
    isInteger(value.occurrence_count) &&
    typeof value.freeze_frame_available === "boolean"
  );
}

function isDiagnosticEvent(value: unknown): value is DiagnosticEvent {
  return (
    isRecord(value) &&
    isInteger(value.sequence) &&
    isInteger(value.timestamp_microseconds) &&
    typeof value.code === "string" &&
    [
      "condition_detected",
      "condition_cleared",
      "dtc_confirmed",
      "dtc_recovered",
      "dtc_cleared",
    ].includes(String(value.event_type)) &&
    (value.prior_status === null || isDiagnosticStatus(value.prior_status)) &&
    (value.new_status === null || isDiagnosticStatus(value.new_status))
  );
}

function isFreezeFrameSignal(value: unknown): boolean {
  return (
    isRecord(value) &&
    isSignalKey(value.key) &&
    (typeof value.value === "number" || typeof value.value === "boolean") &&
    typeof value.unit === "string" &&
    typeof value.source_ecu === "string" &&
    isInteger(value.arbitration_id) &&
    typeof value.arbitration_id_hex === "string" &&
    isInteger(value.timestamp_microseconds) &&
    isInteger(value.telemetry_frame_sequence)
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

export function parseSource(value: unknown): TelemetrySource {
  if (!isSource(value)) {
    throw new Error("Backend returned an invalid telemetry source response");
  }
  return {
    mode: value.mode,
    session_id: value.session_id,
    session_name: value.session_name,
    recording: value.recording,
    recorded_frame_count: value.recorded_frame_count,
  };
}

export function parseCanFrames(value: unknown): CanExplorerFrame[] {
  if (!Array.isArray(value) || !value.every(isCanFrame)) {
    throw new Error("Backend returned an invalid raw CAN frame response");
  }
  return value;
}

export function parseCanFrame(value: unknown): CanExplorerFrame {
  if (!isCanFrame(value)) throw new Error("Backend returned an invalid raw CAN frame response");
  return value;
}

export function parseCanMessages(value: unknown): CanMessageStatistics[] {
  if (!Array.isArray(value) || !value.every(isCanMessageStatistics)) {
    throw new Error("Backend returned invalid CAN message statistics");
  }
  return value;
}

export function parseCanStatistics(value: unknown): CanExplorerStatistics {
  if (!isCanStatistics(value)) throw new Error("Backend returned invalid CAN explorer statistics");
  return value;
}

export function parseCanWebSocketEvent(value: unknown): CanWebSocketEvent {
  if (!isRecord(value) || typeof value.type !== "string") {
    throw new Error("CAN WebSocket sent an invalid event envelope");
  }
  if (
    value.type === "initial_can_snapshot" &&
    Array.isArray(value.frames) &&
    value.frames.every(isCanFrame) &&
    isCanStatistics(value.statistics) &&
    Array.isArray(value.messages) &&
    value.messages.every(isCanMessageStatistics) &&
    isServiceState(value.service_state)
  ) {
    return value as unknown as CanWebSocketEvent;
  }
  if (
    value.type === "can_frame" &&
    isCanFrame(value.frame) &&
    isCanStatistics(value.statistics) &&
    isCanMessageStatistics(value.message_statistics)
  ) {
    return value as unknown as CanWebSocketEvent;
  }
  if (
    value.type === "can_source_state" &&
    isServiceState(value.state) &&
    isNullableString(value.error) &&
    isSource(value.source)
  ) {
    return value as unknown as CanWebSocketEvent;
  }
  throw new Error(`CAN WebSocket sent an invalid ${value.type} event`);
}

export function parseDiagnosticSummary(value: unknown): DiagnosticSummary {
  if (
    !isRecord(value) ||
    !isNullableInteger(value.observation_timestamp_microseconds) ||
    !isNullableInteger(value.latest_telemetry_frame_sequence) ||
    !isInteger(value.retained_event_count) ||
    !isInteger(value.total_event_count) ||
    !isNullableInteger(value.latest_event_sequence) ||
    !isInteger(value.pending_count) ||
    !isInteger(value.active_count) ||
    !isInteger(value.historical_count) ||
    !isInteger(value.cleared_count) ||
    !isServiceState(value.service_state) ||
    !isSource(value.source)
  ) {
    throw new Error("Backend returned an invalid diagnostic summary");
  }
  return value as unknown as DiagnosticSummary;
}

export function parseDiagnosticDtcs(value: unknown): DiagnosticTroubleCode[] {
  if (!Array.isArray(value) || !value.every(isDiagnosticTroubleCode)) {
    throw new Error("Backend returned invalid diagnostic trouble codes");
  }
  return value;
}

export function parseDiagnosticDtc(value: unknown): DiagnosticTroubleCode {
  if (!isDiagnosticTroubleCode(value)) {
    throw new Error("Backend returned an invalid diagnostic trouble code");
  }
  return value;
}

export function parseDiagnosticEvents(value: unknown): DiagnosticEvent[] {
  if (!Array.isArray(value) || !value.every(isDiagnosticEvent)) {
    throw new Error("Backend returned invalid diagnostic events");
  }
  return value;
}

export function parseDiagnosticFreezeFrame(value: unknown): DiagnosticFreezeFrame {
  if (
    !isRecord(value) ||
    typeof value.code !== "string" ||
    !isInteger(value.capture_timestamp_microseconds) ||
    !isInteger(value.telemetry_frame_sequence) ||
    !Array.isArray(value.signals) ||
    !value.signals.every(isFreezeFrameSignal)
  ) {
    throw new Error("Backend returned an invalid diagnostic freeze frame");
  }
  return value as unknown as DiagnosticFreezeFrame;
}

export function parseSessions(value: unknown): SessionSummary[] {
  if (!Array.isArray(value) || !value.every(isSessionSummary)) {
    throw new Error("Backend returned an invalid session list response");
  }
  return value;
}

export function parseSessionDetail(value: unknown): SessionDetail {
  if (!isSessionDetail(value)) {
    throw new Error("Backend returned an invalid session detail response");
  }
  return value;
}

export function parseSessionReplay(value: unknown): SessionReplayResponse {
  if (
    !isRecord(value) ||
    typeof value.session_id !== "string" ||
    !isNullableString(value.session_name) ||
    value.source_mode !== "replay" ||
    value.service_state !== "running"
  ) {
    throw new Error("Backend returned an invalid session replay response");
  }
  return {
    session_id: value.session_id,
    session_name: value.session_name,
    source_mode: "replay",
    service_state: "running",
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
