"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from "react";

import {
  fetchSignalCatalog,
  fetchTelemetrySource,
  fetchTelemetryStatus,
  startSessionReplay,
} from "../../lib/api/client";
import { TUNEROS_WS_URL } from "../../lib/api/config";
import type { TelemetryUpdateEvent } from "../../lib/api/types";
import { parseWebSocketEvent } from "../../lib/api/validation";
import {
  INITIAL_TELEMETRY_STATE,
  type TelemetryClientState,
  telemetryReducer,
} from "../../lib/telemetry/state";

const RECONNECT_DELAYS_MILLISECONDS = [500, 1_000, 2_000, 4_000, 5_000] as const;

const TelemetryContext = createContext<TelemetryClientState | null>(null);
interface TelemetryActions {
  replaySession: (sessionId: string) => Promise<void>;
}
const TelemetryActionsContext = createContext<TelemetryActions | null>(null);

export function TelemetryProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [state, dispatch] = useReducer(telemetryReducer, INITIAL_TELEMETRY_STATE);
  const [connectionGeneration, reconnect] = useReducer((generation: number) => generation + 1, 0);
  const pendingUpdates = useRef<TelemetryUpdateEvent[]>([]);
  const animationFrame = useRef<number | null>(null);

  const flushUpdates = useCallback(() => {
    if (animationFrame.current !== null) {
      cancelAnimationFrame(animationFrame.current);
      animationFrame.current = null;
    }
    if (pendingUpdates.current.length > 0) {
      const updates = pendingUpdates.current;
      pendingUpdates.current = [];
      dispatch({ type: "updates", updates });
    }
  }, []);

  const queueUpdate = useCallback((update: TelemetryUpdateEvent) => {
    pendingUpdates.current.push(update);
    if (animationFrame.current === null) {
      animationFrame.current = requestAnimationFrame(() => {
        animationFrame.current = null;
        const updates = pendingUpdates.current;
        pendingUpdates.current = [];
        dispatch({ type: "updates", updates });
      });
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([fetchTelemetryStatus(), fetchSignalCatalog(), fetchTelemetrySource()])
      .then(([status, catalog, source]) => {
        if (!active) return;
        dispatch({ type: "status", status });
        dispatch({ type: "catalog", catalog });
        dispatch({ type: "source", source });
      })
      .catch((error: unknown) => {
        if (!active) return;
        const message = error instanceof Error ? error.message : "Telemetry backend is unavailable";
        dispatch({ type: "client_error", error: message });
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let retryAttempt = 0;
    let terminalState = false;

    const connect = () => {
      if (!active || terminalState) return;
      dispatch({ type: "connection", state: "connecting", error: null });
      socket = new WebSocket(`${TUNEROS_WS_URL}/api/v1/ws/telemetry`);

      socket.onopen = () => {
        retryAttempt = 0;
        dispatch({ type: "connection", state: "connected", error: null });
      };

      socket.onmessage = (message) => {
        try {
          const event = parseWebSocketEvent(JSON.parse(String(message.data)));
          if (event.type === "initial_snapshot") {
            terminalState = false;
            dispatch({ type: "initial_snapshot", snapshot: event.snapshot });
          } else if (event.type === "telemetry_update") {
            queueUpdate(event);
          } else {
            flushUpdates();
            terminalState = event.state === "completed" || event.state === "failed";
            dispatch({ type: "service_state", state: event.state, error: event.error });
          }
        } catch (error: unknown) {
          const message = error instanceof Error ? error.message : "Malformed telemetry event";
          dispatch({ type: "client_error", error: message });
        }
      };

      socket.onerror = () => {
        dispatch({
          type: "connection",
          state: "error",
          error: "Live telemetry connection failed",
        });
      };

      socket.onclose = () => {
        flushUpdates();
        socket = null;
        if (!active) return;
        if (terminalState) {
          dispatch({ type: "connection", state: "disconnected", error: null });
          return;
        }
        dispatch({
          type: "connection",
          state: "disconnected",
          error: "Live telemetry disconnected; reconnecting",
        });
        const delay =
          RECONNECT_DELAYS_MILLISECONDS[
            Math.min(retryAttempt, RECONNECT_DELAYS_MILLISECONDS.length - 1)
          ];
        retryAttempt += 1;
        retryTimer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      active = false;
      if (retryTimer !== null) clearTimeout(retryTimer);
      if (socket !== null) socket.close();
      flushUpdates();
    };
  }, [connectionGeneration, flushUpdates, queueUpdate]);

  const replaySession = useCallback(async (sessionId: string) => {
    try {
      const response = await startSessionReplay(sessionId);
      dispatch({
        type: "source",
        source: {
          mode: "replay",
          session_id: response.session_id,
          session_name: response.session_name,
          recording: false,
          recorded_frame_count: 0,
        },
      });
      reconnect();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Session replay could not start";
      dispatch({ type: "client_error", error: message });
      throw error;
    }
  }, []);

  const value = useMemo(() => state, [state]);
  const actions = useMemo(() => ({ replaySession }), [replaySession]);
  return (
    <TelemetryActionsContext.Provider value={actions}>
      <TelemetryContext.Provider value={value}>{children}</TelemetryContext.Provider>
    </TelemetryActionsContext.Provider>
  );
}

export function useTelemetryActions(): TelemetryActions {
  const value = useContext(TelemetryActionsContext);
  if (value === null) throw new Error("useTelemetryActions must be used inside TelemetryProvider");
  return value;
}

export function useTelemetry(): TelemetryClientState {
  const value = useContext(TelemetryContext);
  if (value === null) throw new Error("useTelemetry must be used inside TelemetryProvider");
  return value;
}
