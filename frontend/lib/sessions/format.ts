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

export function calibrationDisplayName(session: SessionSummary): string {
  if (session.calibration_id === null || session.calibration_revision === null) {
    return "Unknown / Legacy";
  }
  const name = session.calibration_id === "stage-1"
    ? "Stage 1"
    : session.calibration_id === "stock"
      ? "Stock"
      : session.calibration_id;
  return `${name} r${session.calibration_revision}`;
}
