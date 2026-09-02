import type {
  SignalDefinition,
  SignalKey,
  SignalSample,
  TelemetryServiceState,
  TelemetrySnapshot,
  TelemetryStatistics,
  TelemetryStatus,
  TelemetryUpdateEvent,
} from "../api/types";
import { signalKeyId } from "./signals";

export const CHART_HISTORY_CAPACITY = 180;
export const CHART_SAMPLE_INTERVAL_MICROSECONDS = 50_000;

export type FrontendConnectionState = "connecting" | "connected" | "disconnected" | "error";

export interface ChartPoint {
  timestampMicroseconds: number;
  value: number;
}

export interface TelemetryClientState {
  connectionState: FrontendConnectionState;
  serviceState: TelemetryServiceState;
  serviceError: string | null;
  clientError: string | null;
  streamWarning: string | null;
  catalog: SignalDefinition[];
  samples: Record<string, SignalSample>;
  histories: Record<string, ChartPoint[]>;
  observationTimestampMicroseconds: number | null;
  lastFrameSequence: number | null;
  statistics: TelemetryStatistics;
  initialized: boolean;
}

const EMPTY_STATISTICS: TelemetryStatistics = {
  total_frames: 0,
  total_signal_updates: 0,
  latest_timestamp_microseconds: null,
  last_frame_sequence: null,
  frames_by_message: [],
};

export const INITIAL_TELEMETRY_STATE: TelemetryClientState = {
  connectionState: "connecting",
  serviceState: "stopped",
  serviceError: null,
  clientError: null,
  streamWarning: null,
  catalog: [],
  samples: {},
  histories: {},
  observationTimestampMicroseconds: null,
  lastFrameSequence: null,
  statistics: EMPTY_STATISTICS,
  initialized: false,
};

export type TelemetryAction =
  | { type: "connection"; state: FrontendConnectionState; error?: string | null }
  | { type: "catalog"; catalog: SignalDefinition[] }
  | { type: "status"; status: TelemetryStatus }
  | { type: "initial_snapshot"; snapshot: TelemetrySnapshot }
  | { type: "updates"; updates: TelemetryUpdateEvent[] }
  | { type: "service_state"; state: TelemetryServiceState; error: string | null }
  | { type: "client_error"; error: string };

function appendChartPoint(history: ChartPoint[], sample: SignalSample): ChartPoint[] {
  if (typeof sample.value !== "number") return history;
  const point = {
    timestampMicroseconds: sample.timestamp_microseconds,
    value: sample.value,
  };
  if (history.length === 0) return [point];
  const previous = history[history.length - 1];
  const elapsed = point.timestampMicroseconds - previous.timestampMicroseconds;
  const next =
    elapsed >= CHART_SAMPLE_INTERVAL_MICROSECONDS
      ? [...history, point]
      : [...history.slice(0, -1), point];
  return next.slice(-CHART_HISTORY_CAPACITY);
}

function samplesFromSnapshot(snapshot: TelemetrySnapshot): Record<string, SignalSample> {
  return Object.fromEntries(snapshot.signals.map((sample) => [signalKeyId(sample.key), sample]));
}

function historiesFromSnapshot(snapshot: TelemetrySnapshot): Record<string, ChartPoint[]> {
  const histories: Record<string, ChartPoint[]> = {};
  for (const sample of snapshot.signals) {
    if (typeof sample.value === "number") {
      histories[signalKeyId(sample.key)] = [
        { timestampMicroseconds: sample.timestamp_microseconds, value: sample.value },
      ];
    }
  }
  return histories;
}

function applyUpdate(
  state: TelemetryClientState,
  update: TelemetryUpdateEvent,
): TelemetryClientState {
  if (state.lastFrameSequence !== null && update.frame_sequence <= state.lastFrameSequence) {
    return {
      ...state,
      streamWarning: `Ignored frame sequence ${update.frame_sequence}; latest is ${state.lastFrameSequence}.`,
    };
  }

  const expectedSequence = state.lastFrameSequence === null ? null : state.lastFrameSequence + 1;
  const streamWarning =
    expectedSequence !== null && update.frame_sequence !== expectedSequence
      ? `Stream gap: expected frame ${expectedSequence}, received ${update.frame_sequence}.`
      : state.streamWarning;
  const samples = { ...state.samples };
  const histories = { ...state.histories };
  for (const sample of update.signals) {
    const id = signalKeyId(sample.key);
    samples[id] = sample;
    histories[id] = appendChartPoint(histories[id] ?? [], sample);
  }
  const frameCountIndex = state.statistics.frames_by_message.findIndex(
    (count) => count.arbitration_id === update.arbitration_id,
  );
  const framesByMessage = state.statistics.frames_by_message.map((count, index) =>
    index === frameCountIndex ? { ...count, frames: count.frames + 1 } : count,
  );
  if (frameCountIndex === -1) {
    framesByMessage.push({
      arbitration_id: update.arbitration_id,
      arbitration_id_hex: update.arbitration_id_hex,
      message_name: update.message_name,
      frames: 1,
    });
  }

  return {
    ...state,
    samples,
    histories,
    observationTimestampMicroseconds: update.timestamp_microseconds,
    lastFrameSequence: update.frame_sequence,
    statistics: {
      total_frames: Math.max(state.statistics.total_frames + 1, update.frame_sequence + 1),
      total_signal_updates: state.statistics.total_signal_updates + update.signals.length,
      latest_timestamp_microseconds: update.timestamp_microseconds,
      last_frame_sequence: update.frame_sequence,
      frames_by_message: framesByMessage,
    },
    streamWarning,
    initialized: true,
  };
}

export function telemetryReducer(
  state: TelemetryClientState,
  action: TelemetryAction,
): TelemetryClientState {
  switch (action.type) {
    case "connection":
      return {
        ...state,
        connectionState: action.state,
        clientError: action.error === undefined ? state.clientError : action.error,
      };
    case "catalog":
      return { ...state, catalog: action.catalog };
    case "status":
      return {
        ...state,
        serviceState: action.status.service_state,
        serviceError: action.status.last_error,
      };
    case "initial_snapshot":
      return {
        ...state,
        samples: samplesFromSnapshot(action.snapshot),
        histories: historiesFromSnapshot(action.snapshot),
        observationTimestampMicroseconds: action.snapshot.observation_timestamp_microseconds,
        lastFrameSequence: action.snapshot.last_frame_sequence,
        statistics: action.snapshot.statistics,
        streamWarning: null,
        initialized: true,
      };
    case "updates":
      return action.updates.reduce(applyUpdate, state);
    case "service_state":
      return {
        ...state,
        serviceState: action.state,
        serviceError: action.error,
      };
    case "client_error":
      return { ...state, clientError: action.error };
  }
}

export function selectSample(
  state: TelemetryClientState,
  key: SignalKey,
): SignalSample | undefined {
  return state.samples[signalKeyId(key)];
}

export function selectHistory(state: TelemetryClientState, key: SignalKey): ChartPoint[] {
  return state.histories[signalKeyId(key)] ?? [];
}
