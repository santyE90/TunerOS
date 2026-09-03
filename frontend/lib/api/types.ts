export type SignalValue = number | boolean;
export type SignalFreshness = "fresh" | "stale";
export type TelemetryServiceState =
  | "stopped"
  | "connecting"
  | "running"
  | "completed"
  | "failed";
export type TelemetrySourceMode = "live" | "replay";

export interface SignalKey {
  message_name: string;
  signal_name: string;
}

export interface SignalDefinition {
  key: SignalKey;
  signal_name: string;
  message_name: string;
  arbitration_id: number;
  arbitration_id_hex: string;
  source_ecu: string;
  unit: string;
  expected_period_microseconds: number;
}

export interface SignalSample {
  key: SignalKey;
  value: SignalValue;
  timestamp_microseconds: number;
  frame_sequence: number;
  arbitration_id: number;
  arbitration_id_hex: string;
  message_name: string;
  source_ecu: string;
  unit: string;
  freshness: SignalFreshness | null;
}

export interface MessageFrameCount {
  arbitration_id: number;
  arbitration_id_hex: string;
  message_name: string;
  frames: number;
}

export interface TelemetryStatistics {
  total_frames: number;
  total_signal_updates: number;
  latest_timestamp_microseconds: number | null;
  last_frame_sequence: number | null;
  frames_by_message: MessageFrameCount[];
}

export interface TelemetrySnapshot {
  observation_timestamp_microseconds: number | null;
  last_frame_sequence: number | null;
  signals: SignalSample[];
  statistics: TelemetryStatistics;
}

export interface TelemetryStatus {
  service_state: TelemetryServiceState;
  gateway_connected: boolean;
  last_error: string | null;
  latest_timestamp_microseconds: number | null;
  total_frames: number;
  total_signal_updates: number;
}

export interface TelemetrySource {
  mode: TelemetrySourceMode;
  session_id: string | null;
  session_name: string | null;
  recording: boolean;
  recorded_frame_count: number;
}

export type CanDecodeStatus = "decoded" | "unknown" | "error";

export interface CanDecodedSignal {
  signal_name: string;
  value: SignalValue;
  unit: string;
}

export interface CanExplorerFrame {
  sequence: number;
  timestamp_microseconds: number;
  arbitration_id: number;
  arbitration_id_hex: string;
  dlc: number;
  payload: number[];
  payload_hex: string;
  message_name: string | null;
  source_ecu: string | null;
  expected_period_microseconds: number | null;
  decode_status: CanDecodeStatus;
  decode_error: string | null;
  decoded_signals: CanDecodedSignal[];
}

export interface CanMessageStatistics {
  arbitration_id: number;
  arbitration_id_hex: string;
  message_name: string | null;
  source_ecu: string | null;
  retained_frame_count: number;
  total_frame_count: number;
  first_timestamp_microseconds: number;
  latest_timestamp_microseconds: number;
  expected_period_microseconds: number | null;
  observed_average_period_microseconds: number | null;
  observed_frequency_hz: number | null;
  latest_dlc: number;
}

export interface CanExplorerStatistics {
  retained_frame_count: number;
  total_frame_count: number;
  unique_id_count: number;
  oldest_retained_timestamp_microseconds: number | null;
  newest_retained_timestamp_microseconds: number | null;
  last_sequence: number | null;
  source: TelemetrySource;
}

export interface InitialCanSnapshotEvent {
  type: "initial_can_snapshot";
  frames: CanExplorerFrame[];
  statistics: CanExplorerStatistics;
  messages: CanMessageStatistics[];
  service_state: TelemetryServiceState;
}

export interface CanFrameEvent {
  type: "can_frame";
  frame: CanExplorerFrame;
  statistics: CanExplorerStatistics;
  message_statistics: CanMessageStatistics;
}

export interface CanSourceStateEvent {
  type: "can_source_state";
  state: TelemetryServiceState;
  error: string | null;
  source: TelemetrySource;
}

export type DiagnosticStatus = "pending" | "active" | "historical" | "cleared";
export type DiagnosticSeverity = "info" | "warning" | "critical";
export type DiagnosticEventType =
  | "condition_detected"
  | "condition_cleared"
  | "dtc_confirmed"
  | "dtc_recovered"
  | "dtc_cleared";

export interface DiagnosticDefinition {
  code: string;
  rule_id: string;
  name: string;
  description: string;
  severity: DiagnosticSeverity;
  source_system: string;
  required_signals: SignalKey[];
  confirmation_duration_microseconds: number;
  recovery_duration_microseconds: number;
  activation_description: string;
  recovery_description: string;
}

export interface DiagnosticTroubleCode {
  definition: DiagnosticDefinition;
  status: DiagnosticStatus;
  first_detected_timestamp_microseconds: number;
  confirmed_timestamp_microseconds: number | null;
  last_seen_timestamp_microseconds: number;
  resolved_timestamp_microseconds: number | null;
  cleared_timestamp_microseconds: number | null;
  occurrence_count: number;
  freeze_frame_available: boolean;
}

export interface DiagnosticSummary {
  observation_timestamp_microseconds: number | null;
  latest_telemetry_frame_sequence: number | null;
  retained_event_count: number;
  total_event_count: number;
  latest_event_sequence: number | null;
  pending_count: number;
  active_count: number;
  historical_count: number;
  cleared_count: number;
  service_state: TelemetryServiceState;
  source: TelemetrySource;
}

export interface DiagnosticEvent {
  sequence: number;
  timestamp_microseconds: number;
  code: string;
  event_type: DiagnosticEventType;
  prior_status: DiagnosticStatus | null;
  new_status: DiagnosticStatus | null;
}

export interface FreezeFrameSignal {
  key: SignalKey;
  value: SignalValue;
  unit: string;
  source_ecu: string;
  arbitration_id: number;
  arbitration_id_hex: string;
  timestamp_microseconds: number;
  telemetry_frame_sequence: number;
}

export interface DiagnosticFreezeFrame {
  code: string;
  capture_timestamp_microseconds: number;
  telemetry_frame_sequence: number;
  signals: FreezeFrameSignal[];
}

export type CanWebSocketEvent =
  | InitialCanSnapshotEvent
  | CanFrameEvent
  | CanSourceStateEvent;

export interface SessionSummary {
  session_id: string;
  name: string | null;
  created_at_utc: string;
  scenario: string | null;
  status: "complete";
  frame_count: number;
  duration_microseconds: number;
  dbc_compatible: boolean;
}

export interface SessionDetail extends SessionSummary {
  format_name: string;
  format_version: number;
  vehicle_profile_id: string;
  can_network: string;
  dbc_name: string;
  dbc_sha256: string;
  frames_sha256: string;
  first_timestamp_microseconds: number | null;
  last_timestamp_microseconds: number | null;
}

export interface SessionReplayResponse {
  session_id: string;
  session_name: string | null;
  source_mode: "replay";
  service_state: "running";
}

export interface SignalResponse {
  definition: SignalDefinition;
  sample: SignalSample | null;
  freshness: SignalFreshness | null;
}

export interface SignalHistoryResponse {
  definition: SignalDefinition;
  samples: SignalSample[];
}

export interface InitialSnapshotEvent {
  type: "initial_snapshot";
  snapshot: TelemetrySnapshot;
}

export interface TelemetryUpdateEvent {
  type: "telemetry_update";
  timestamp_microseconds: number;
  frame_sequence: number;
  arbitration_id: number;
  arbitration_id_hex: string;
  message_name: string;
  source_ecu: string;
  signals: SignalSample[];
}

export interface ServiceStateEvent {
  type: "service_state";
  state: TelemetryServiceState;
  error: string | null;
}

export type TelemetryWebSocketEvent =
  | InitialSnapshotEvent
  | TelemetryUpdateEvent
  | ServiceStateEvent;
