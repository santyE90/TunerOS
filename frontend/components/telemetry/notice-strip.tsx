"use client";

import { useTelemetry } from "./telemetry-provider";

export function NoticeStrip() {
  const telemetry = useTelemetry();
  if (
    telemetry.serviceState === "running" &&
    telemetry.clientError === null &&
    telemetry.streamWarning === null
  ) {
    return null;
  }

  let tone = "info";
  let title = "Waiting for telemetry";
  let message = "The dashboard will populate when the local telemetry service publishes signals.";
  if (telemetry.serviceState === "completed") {
    tone = "complete";
    title = telemetry.source.mode === "replay" ? "Replay complete" : "Simulation complete";
    message = "Final values and chart history are retained for inspection.";
  } else if (telemetry.serviceState === "failed") {
    tone = "error";
    title = "Telemetry service failed";
    message = telemetry.serviceError ?? "The backend reported a gateway or ingestion failure.";
  } else if (telemetry.clientError !== null) {
    tone = "error";
    title = "Backend unavailable";
    message = telemetry.clientError;
  } else if (telemetry.streamWarning !== null) {
    tone = "warning";
    title = "Stream integrity warning";
    message = telemetry.streamWarning;
  }

  return (
    <aside className={`notice-strip ${tone}`} role={tone === "error" ? "alert" : "status"}>
      <strong>{title}</strong>
      <span>{message}</span>
    </aside>
  );
}
