import type {
  InvestigationSignalSeries,
  SignalKey,
  SignalSample,
} from "../api/types";

export const DEFAULT_INVESTIGATION_SPAN_MICROSECONDS = 2_000_000;
export const MAX_INVESTIGATION_WINDOW_MICROSECONDS = 30_000_000;
export const MAX_INVESTIGATION_SIGNALS = 6;
export const RAW_CURSOR_RADIUS_MICROSECONDS = 100_000;

export interface InvestigationUrlState {
  centerMicroseconds?: number;
  beforeMicroseconds: number;
  afterMicroseconds: number;
  baselineSessionId?: string;
  baselineCenterMicroseconds?: number;
  diagnosticCode?: string;
  signals: string[];
}

function optionalInteger(parameters: URLSearchParams, name: string): number | undefined {
  const value = parameters.get(name);
  if (value === null) return undefined;
  if (!/^\d+$/.test(value)) throw new Error(`${name} must be a non-negative integer`);
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed)) throw new Error(`${name} exceeds safe integer range`);
  return parsed;
}

export function parseInvestigationUrl(parameters: URLSearchParams): InvestigationUrlState {
  const beforeMicroseconds =
    optionalInteger(parameters, "before") ?? DEFAULT_INVESTIGATION_SPAN_MICROSECONDS;
  const afterMicroseconds =
    optionalInteger(parameters, "after") ?? DEFAULT_INVESTIGATION_SPAN_MICROSECONDS;
  if (beforeMicroseconds + afterMicroseconds > MAX_INVESTIGATION_WINDOW_MICROSECONDS) {
    throw new Error("Investigation window cannot exceed 30 seconds");
  }
  const signals = parameters.getAll("signal");
  if (signals.length > MAX_INVESTIGATION_SIGNALS || new Set(signals).size !== signals.length) {
    throw new Error("Investigation signal selection must contain up to six unique signals");
  }
  return {
    centerMicroseconds: optionalInteger(parameters, "t"),
    beforeMicroseconds,
    afterMicroseconds,
    baselineSessionId: parameters.get("baseline") ?? undefined,
    baselineCenterMicroseconds: optionalInteger(parameters, "baseline_t"),
    diagnosticCode: parameters.get("code") ?? undefined,
    signals,
  };
}

export function canonicalSignal(key: SignalKey): string {
  return `${key.message_name}.${key.signal_name}`;
}

export function buildInvestigationHref(
  sessionId: string,
  timestampMicroseconds?: number,
  diagnosticCode?: string,
): string {
  const parameters = new URLSearchParams();
  if (timestampMicroseconds !== undefined) parameters.set("t", String(timestampMicroseconds));
  if (diagnosticCode !== undefined) parameters.set("code", diagnosticCode);
  const suffix = parameters.size === 0 ? "" : `?${parameters.toString()}`;
  return `/sessions/${encodeURIComponent(sessionId)}/investigate${suffix}`;
}

export function latestAtOrBefore(
  series: InvestigationSignalSeries,
  context: SignalSample | undefined,
  cursorTimestampMicroseconds: number,
): SignalSample | undefined {
  for (let index = series.samples.length - 1; index >= 0; index -= 1) {
    const sample = series.samples[index];
    if (sample.timestamp_microseconds <= cursorTimestampMicroseconds) return sample;
  }
  return context?.timestamp_microseconds !== undefined &&
    context.timestamp_microseconds <= cursorTimestampMicroseconds
    ? context
    : undefined;
}

export function toggleInvestigationSignal(selected: string[], signal: string): string[] {
  if (selected.includes(signal)) return selected.filter((item) => item !== signal);
  if (selected.length >= MAX_INVESTIGATION_SIGNALS) {
    throw new Error(`Select at most ${MAX_INVESTIGATION_SIGNALS} signals`);
  }
  return [...selected, signal];
}

export function relativeTimestampMicroseconds(
  timestampMicroseconds: number,
  centerTimestampMicroseconds: number,
): number {
  return timestampMicroseconds - centerTimestampMicroseconds;
}
