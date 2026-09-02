import type { SignalSample } from "../api/types";

export function metersPerSecondToKilometersPerHour(value: number): number {
  return value * 3.6;
}

export function normalizedToPercent(value: number): number {
  return value * 100;
}

export function simulationSeconds(timestampMicroseconds: number | null): number | null {
  return timestampMicroseconds === null ? null : timestampMicroseconds / 1_000_000;
}

export function formatSimulationTime(timestampMicroseconds: number | null): string {
  const seconds = simulationSeconds(timestampMicroseconds);
  return seconds === null ? "—" : `${seconds.toFixed(3)} s`;
}

export function formatRawValue(sample: SignalSample | undefined): string {
  if (sample === undefined) return "—";
  if (typeof sample.value === "boolean") return sample.value ? "true" : "false";
  if (sample.unit === "gear") return sample.value === 0 ? "N" : Math.round(sample.value).toString();
  if (sample.unit === "rpm") return Math.round(sample.value).toLocaleString("en-US");
  return sample.value.toFixed(sample.unit === "normalized" ? 3 : 1);
}
