"use client";

import { formatSimulationTime } from "../../lib/telemetry/format";
import { useTelemetry } from "./telemetry-provider";

function stateTone(state: string): string {
  if (state === "connected" || state === "running") return "positive";
  if (state === "error" || state === "failed") return "negative";
  if (state === "completed") return "complete";
  return "neutral";
}

export function StatusBar() {
  const telemetry = useTelemetry();
  const sources = new Set(Object.values(telemetry.samples).map((sample) => sample.source_ecu));

  return (
    <section className="status-bar" aria-label="Telemetry connection status">
      <div className="status-item">
        <span className={`status-dot ${stateTone(telemetry.connectionState)}`} aria-hidden="true" />
        <span>Backend</span>
        <strong>{telemetry.connectionState}</strong>
      </div>
      <div className="status-item">
        <span
          className={`status-dot ${telemetry.source.recording ? "complete" : "positive"}`}
          aria-hidden="true"
        />
        <span>Source</span>
        <strong>
          {telemetry.source.recording
            ? "recording"
            : telemetry.source.mode === "replay"
              ? `replay${telemetry.source.session_name ? ` · ${telemetry.source.session_name}` : ""}`
              : "live"}
        </strong>
      </div>
      <div className="status-item">
        <span className={`status-dot ${stateTone(telemetry.serviceState)}`} aria-hidden="true" />
        <span>Service</span>
        <strong>{telemetry.serviceState}</strong>
      </div>
      <div className="status-item mono">
        <span>Simulation</span>
        <strong>{formatSimulationTime(telemetry.observationTimestampMicroseconds)}</strong>
      </div>
      <div className="status-item mono">
        <span>Frame</span>
        <strong>
          {telemetry.lastFrameSequence === null
            ? "—"
            : telemetry.lastFrameSequence.toLocaleString("en-US")}
        </strong>
      </div>
      <div className="status-sources" aria-label="Observed ECU sources">
        <span className={sources.has("TunerOsSimulatedDme") ? "source-chip online" : "source-chip"}>
          DME
        </span>
        <span className={sources.has("TunerOsSimulatedDsc") ? "source-chip online" : "source-chip"}>
          DSC
        </span>
      </div>
    </section>
  );
}
