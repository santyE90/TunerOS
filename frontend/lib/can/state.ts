import type {
  CanExplorerFrame,
  CanExplorerStatistics,
  CanFrameEvent,
  CanMessageStatistics,
  InitialCanSnapshotEvent,
  TelemetryServiceState,
  TelemetrySource,
} from "../api/types";

export const CAN_CLIENT_BUFFER_CAPACITY = 1_000;

export interface CanExplorerClientState {
  connectionState: "connecting" | "connected" | "disconnected" | "error";
  serviceState: TelemetryServiceState;
  source: TelemetrySource;
  currentFrames: CanExplorerFrame[];
  displayedFrames: CanExplorerFrame[];
  messages: Record<string, CanMessageStatistics>;
  statistics: CanExplorerStatistics;
  frozen: boolean;
  framesPassedWhileFrozen: number;
  streamWarning: string | null;
  error: string | null;
  initialized: boolean;
}

const EMPTY_SOURCE: TelemetrySource = {
  mode: "live",
  session_id: null,
  session_name: null,
  recording: false,
  recorded_frame_count: 0,
};

const EMPTY_STATISTICS: CanExplorerStatistics = {
  retained_frame_count: 0,
  total_frame_count: 0,
  unique_id_count: 0,
  oldest_retained_timestamp_microseconds: null,
  newest_retained_timestamp_microseconds: null,
  last_sequence: null,
  source: EMPTY_SOURCE,
};

export const INITIAL_CAN_EXPLORER_STATE: CanExplorerClientState = {
  connectionState: "connecting",
  serviceState: "stopped",
  source: EMPTY_SOURCE,
  currentFrames: [],
  displayedFrames: [],
  messages: {},
  statistics: EMPTY_STATISTICS,
  frozen: false,
  framesPassedWhileFrozen: 0,
  streamWarning: null,
  error: null,
  initialized: false,
};

export type CanExplorerAction =
  | { type: "connection"; state: CanExplorerClientState["connectionState"]; error?: string | null }
  | { type: "initial"; event: InitialCanSnapshotEvent }
  | { type: "frames"; events: CanFrameEvent[] }
  | { type: "source_state"; state: TelemetryServiceState; source: TelemetrySource; error: string | null }
  | { type: "toggle_freeze" }
  | { type: "client_error"; error: string };

function appendBounded(
  frames: CanExplorerFrame[],
  frame: CanExplorerFrame,
): CanExplorerFrame[] {
  return [...frames, frame].slice(-CAN_CLIENT_BUFFER_CAPACITY);
}

function applyFrame(state: CanExplorerClientState, event: CanFrameEvent): CanExplorerClientState {
  const latest = state.statistics.last_sequence;
  if (latest !== null && event.frame.sequence <= latest) {
    return {
      ...state,
      streamWarning: `Ignored raw sequence ${event.frame.sequence}; latest is ${latest}.`,
    };
  }
  const expected = latest === null ? null : latest + 1;
  const streamWarning =
    expected !== null && event.frame.sequence !== expected
      ? `Raw stream gap: expected ${expected}, received ${event.frame.sequence}.`
      : state.streamWarning;
  const currentFrames = appendBounded(state.currentFrames, event.frame);
  return {
    ...state,
    currentFrames,
    displayedFrames: state.frozen ? state.displayedFrames : currentFrames,
    messages: {
      ...state.messages,
      [String(event.message_statistics.arbitration_id)]: event.message_statistics,
    },
    statistics: event.statistics,
    source: event.statistics.source,
    framesPassedWhileFrozen: state.frozen
      ? state.framesPassedWhileFrozen + (latest === null ? 1 : event.frame.sequence - latest)
      : 0,
    streamWarning,
    initialized: true,
  };
}

export function canExplorerReducer(
  state: CanExplorerClientState,
  action: CanExplorerAction,
): CanExplorerClientState {
  switch (action.type) {
    case "connection":
      return {
        ...state,
        connectionState: action.state,
        error: action.error === undefined ? state.error : action.error,
      };
    case "initial": {
      const frames = action.event.frames.slice(-CAN_CLIENT_BUFFER_CAPACITY);
      return {
        ...state,
        serviceState: action.event.service_state,
        source: action.event.statistics.source,
        currentFrames: frames,
        displayedFrames: state.frozen ? state.displayedFrames : frames,
        messages: Object.fromEntries(
          action.event.messages.map((message) => [String(message.arbitration_id), message]),
        ),
        statistics: action.event.statistics,
        framesPassedWhileFrozen: state.frozen
          ? Math.max(
              0,
              (action.event.statistics.last_sequence ?? -1) -
                (state.statistics.last_sequence ?? -1),
            )
          : 0,
        streamWarning: null,
        initialized: true,
      };
    }
    case "frames":
      return action.events.reduce(applyFrame, state);
    case "source_state":
      return {
        ...state,
        serviceState: action.state,
        source: action.source,
        error: action.error,
      };
    case "toggle_freeze":
      return state.frozen
        ? {
            ...state,
            frozen: false,
            displayedFrames: state.currentFrames,
            framesPassedWhileFrozen: 0,
          }
        : { ...state, frozen: true };
    case "client_error":
      return { ...state, error: action.error };
  }
}

export interface CanFrameFilters {
  canId: string;
  messageName: string;
  sourceEcu: string;
  text: string;
}

export function filterCanFrames(
  frames: CanExplorerFrame[],
  filters: CanFrameFilters,
): CanExplorerFrame[] {
  const id = filters.canId.trim().toLowerCase();
  const message = filters.messageName.trim().toLowerCase();
  const source = filters.sourceEcu.trim().toLowerCase();
  const text = filters.text.trim().toLowerCase();
  return frames.filter((frame) => {
    const messageName = frame.message_name?.toLowerCase() ?? "unknown";
    const sourceEcu = frame.source_ecu?.toLowerCase() ?? "";
    return (
      (!id || frame.arbitration_id_hex.toLowerCase().includes(id)) &&
      (!message || messageName.includes(message)) &&
      (!source || sourceEcu.includes(source)) &&
      (!text ||
        `${frame.payload_hex} ${messageName} ${frame.arbitration_id_hex}`
          .toLowerCase()
          .includes(text))
    );
  });
}
