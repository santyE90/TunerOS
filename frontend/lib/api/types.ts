export type SignalValue = number | boolean;
export type SignalFreshness = "fresh" | "stale";
export type TelemetryServiceState =
  | "stopped"
  | "connecting"
  | "running"
  | "completed"
  | "failed";

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
