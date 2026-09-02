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

import { fetchSignalCatalog, fetchTelemetryStatus } from "../../lib/api/client";
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

export function TelemetryProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [state, dispatch] = useReducer(telemetryReducer, INITIAL_TELEMETRY_STATE);
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
    Promise.all([fetchTelemetryStatus(), fetchSignalCatalog()])
      .then(([status, catalog]) => {
        if (!active) return;
        dispatch({ type: "status", status });
        dispatch({ type: "catalog", catalog });
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
  }, [flushUpdates, queueUpdate]);

  const value = useMemo(() => state, [state]);
  return <TelemetryContext.Provider value={value}>{children}</TelemetryContext.Provider>;
}

export function useTelemetry(): TelemetryClientState {
  const value = useContext(TelemetryContext);
  if (value === null) throw new Error("useTelemetry must be used inside TelemetryProvider");
  return value;
}
