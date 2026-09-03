import type { SignalValue } from "../api/types";

export function formatDiagnosticTime(timestampMicroseconds: number | null): string {
  return timestampMicroseconds === null
    ? "—"
    : `${(timestampMicroseconds / 1_000_000).toFixed(6)} s`;
}

export function formatDiagnosticValue(value: SignalValue): string {
  return typeof value === "boolean" ? (value ? "true" : "false") : String(value);
}
