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

import type { CanFrameEvent } from "../../lib/api/types";
import { TUNEROS_WS_URL } from "../../lib/api/config";
import { parseCanWebSocketEvent } from "../../lib/api/validation";
import {
  CAN_CLIENT_BUFFER_CAPACITY,
  canExplorerReducer,
  INITIAL_CAN_EXPLORER_STATE,
  type CanExplorerClientState,
} from "../../lib/can/state";

const CanExplorerContext = createContext<CanExplorerClientState | null>(null);
const CanExplorerActionsContext = createContext<{ toggleFreeze: () => void } | null>(null);

export function CanExplorerProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [state, dispatch] = useReducer(canExplorerReducer, INITIAL_CAN_EXPLORER_STATE);
  const pending = useRef<CanFrameEvent[]>([]);
  const animationFrame = useRef<number | null>(null);

  const flush = useCallback(() => {
    if (animationFrame.current !== null) {
      cancelAnimationFrame(animationFrame.current);
      animationFrame.current = null;
    }
    if (pending.current.length > 0) {
      const events = pending.current;
      pending.current = [];
      dispatch({ type: "frames", events });
    }
  }, []);

  const queue = useCallback((event: CanFrameEvent) => {
    pending.current = [...pending.current, event].slice(-CAN_CLIENT_BUFFER_CAPACITY);
    if (animationFrame.current === null) {
      animationFrame.current = requestAnimationFrame(() => {
        animationFrame.current = null;
        const events = pending.current;
        pending.current = [];
        dispatch({ type: "frames", events });
      });
    }
  }, []);

  useEffect(() => {
    let active = true;
    let terminal = false;
    const socket = new WebSocket(`${TUNEROS_WS_URL}/api/v1/ws/can`);
    dispatch({ type: "connection", state: "connecting", error: null });

    socket.onopen = () => {
      if (!active) return;
      dispatch({ type: "connection", state: "connected", error: null });
    };
    socket.onmessage = (message) => {
      if (!active) return;
      try {
        const event = parseCanWebSocketEvent(JSON.parse(String(message.data)));
        if (event.type === "initial_can_snapshot") {
          pending.current = [];
          dispatch({ type: "initial", event });
        } else if (event.type === "can_frame") {
          queue(event);
        } else {
          flush();
          terminal = ["completed", "failed", "stopped"].includes(event.state);
          dispatch({
            type: "source_state",
            state: event.state,
            source: event.source,
            error: event.error,
          });
        }
      } catch (error: unknown) {
        dispatch({
          type: "client_error",
          error: error instanceof Error ? error.message : "Malformed CAN explorer event",
        });
      }
    };
    socket.onerror = () => {
      if (!active) return;
      dispatch({ type: "connection", state: "error", error: "Raw CAN connection failed" });
    };
    socket.onclose = () => {
      flush();
      if (!active) return;
      dispatch({
        type: "connection",
        state: "disconnected",
        error: terminal ? null : "Raw CAN connection closed",
      });
    };

    return () => {
      active = false;
      socket.close();
      if (animationFrame.current !== null) cancelAnimationFrame(animationFrame.current);
      animationFrame.current = null;
      pending.current = [];
    };
  }, [flush, queue]);

  const actions = useMemo(
    () => ({ toggleFreeze: () => dispatch({ type: "toggle_freeze" }) }),
    [],
  );
  return (
    <CanExplorerActionsContext.Provider value={actions}>
      <CanExplorerContext.Provider value={state}>{children}</CanExplorerContext.Provider>
    </CanExplorerActionsContext.Provider>
  );
}

export function useCanExplorer(): CanExplorerClientState {
  const context = useContext(CanExplorerContext);
  if (context === null) throw new Error("useCanExplorer must be used inside CanExplorerProvider");
  return context;
}

export function useCanExplorerActions() {
  const context = useContext(CanExplorerActionsContext);
  if (context === null) {
    throw new Error("useCanExplorerActions must be used inside CanExplorerProvider");
  }
  return context;
}
