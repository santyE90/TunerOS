import { TUNEROS_API_URL } from "./config";
import type {
  SignalDefinition,
  SignalHistoryResponse,
  SignalResponse,
  TelemetrySnapshot,
  TelemetryStatus,
  TelemetrySource,
  SessionDetail,
  SessionReplayResponse,
  SessionSummary,
} from "./types";
import {
  parseCatalog,
  parseSessionDetail,
  parseSessionReplay,
  parseSessions,
  parseSignalHistoryResponse,
  parseSignalResponse,
  parseSnapshot,
  parseStatus,
  parseSource,
} from "./validation";

export class TelemetryApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "TelemetryApiError";
  }
}

async function getJson(path: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${TUNEROS_API_URL}${path}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new TelemetryApiError("Telemetry backend is unavailable");
  }
  if (!response.ok) {
    throw new TelemetryApiError(`Telemetry request failed (${response.status})`, response.status);
  }
  try {
    return await response.json();
  } catch {
    throw new TelemetryApiError("Telemetry backend returned malformed JSON");
  }
}

async function postJson(path: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${TUNEROS_API_URL}${path}`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new TelemetryApiError("Telemetry backend is unavailable");
  }
  if (!response.ok) {
    throw new TelemetryApiError(`Telemetry request failed (${response.status})`, response.status);
  }
  try {
    return await response.json();
  } catch {
    throw new TelemetryApiError("Telemetry backend returned malformed JSON");
  }
}

export async function fetchTelemetryStatus(): Promise<TelemetryStatus> {
  return parseStatus(await getJson("/api/v1/status"));
}

export async function fetchTelemetrySource(): Promise<TelemetrySource> {
  return parseSource(await getJson("/api/v1/source"));
}

export async function fetchSessions(): Promise<SessionSummary[]> {
  return parseSessions(await getJson("/api/v1/sessions"));
}

export async function fetchSessionDetail(sessionId: string): Promise<SessionDetail> {
  return parseSessionDetail(await getJson(`/api/v1/sessions/${encodeURIComponent(sessionId)}`));
}

export async function startSessionReplay(sessionId: string): Promise<SessionReplayResponse> {
  return parseSessionReplay(
    await postJson(`/api/v1/sessions/${encodeURIComponent(sessionId)}/replay`),
  );
}

export async function fetchSignalCatalog(): Promise<SignalDefinition[]> {
  return parseCatalog(await getJson("/api/v1/catalog"));
}

export async function fetchTelemetrySnapshot(): Promise<TelemetrySnapshot> {
  return parseSnapshot(await getJson("/api/v1/telemetry"));
}

export async function fetchSignal(
  messageName: string,
  signalName: string,
): Promise<SignalResponse> {
  return parseSignalResponse(await getJson(
    `/api/v1/messages/${encodeURIComponent(messageName)}/signals/${encodeURIComponent(signalName)}`,
  ));
}

export async function fetchSignalHistory(
  messageName: string,
  signalName: string,
  limit?: number,
): Promise<SignalHistoryResponse> {
  const suffix = limit === undefined ? "" : `?limit=${limit}`;
  return parseSignalHistoryResponse(await getJson(
    `/api/v1/messages/${encodeURIComponent(messageName)}/signals/${encodeURIComponent(signalName)}/history${suffix}`,
  ));
}
