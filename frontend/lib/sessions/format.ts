import type { SessionSummary } from "../api/types";

export function sessionDisplayName(session: SessionSummary): string {
  return session.name ?? `Session ${session.session_id.slice(0, 8)}`;
}

export function formatSessionDuration(durationMicroseconds: number): string {
  return `${(durationMicroseconds / 1_000_000).toFixed(3)} s`;
}

export function formatFrameCount(frameCount: number): string {
  return frameCount.toLocaleString("en-US");
}
