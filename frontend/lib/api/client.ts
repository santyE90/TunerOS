import { TUNEROS_API_URL } from "./config";
import type {
  CanExplorerFrame,
  CanExplorerStatistics,
  CanMessageStatistics,
  DiagnosticEvent,
  DiagnosticFreezeFrame,
  DiagnosticStatus,
  DiagnosticSummary,
  DiagnosticTroubleCode,
  InvestigationComparison,
  InvestigationResult,
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
  parseCanFrame,
  parseCanFrames,
  parseCanMessages,
  parseCanStatistics,
  parseDiagnosticDtc,
  parseDiagnosticDtcs,
  parseDiagnosticEvents,
  parseDiagnosticFreezeFrame,
  parseDiagnosticSummary,
  parseInvestigation,
  parseInvestigationComparison,
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

export interface CanFrameQuery {
  limit?: number;
  arbitrationId?: number;
  messageName?: string;
  sourceEcu?: string;
}

export async function fetchCanFrames(query: CanFrameQuery = {}): Promise<CanExplorerFrame[]> {
  const parameters = new URLSearchParams();
  if (query.limit !== undefined) parameters.set("limit", String(query.limit));
  if (query.arbitrationId !== undefined) {
    parameters.set("arbitration_id", String(query.arbitrationId));
  }
  if (query.messageName !== undefined) parameters.set("message_name", query.messageName);
  if (query.sourceEcu !== undefined) parameters.set("source_ecu", query.sourceEcu);
  const suffix = parameters.size === 0 ? "" : `?${parameters.toString()}`;
  return parseCanFrames(await getJson(`/api/v1/can/frames${suffix}`));
}

export async function fetchCanFrame(sequence: number): Promise<CanExplorerFrame> {
  return parseCanFrame(await getJson(`/api/v1/can/frames/${sequence}`));
}

export async function fetchCanStatistics(): Promise<CanExplorerStatistics> {
  return parseCanStatistics(await getJson("/api/v1/can/statistics"));
}

export async function fetchCanMessages(): Promise<CanMessageStatistics[]> {
  return parseCanMessages(await getJson("/api/v1/can/messages"));
}

export async function fetchDiagnosticSummary(): Promise<DiagnosticSummary> {
  return parseDiagnosticSummary(await getJson("/api/v1/diagnostics"));
}

export async function fetchDiagnosticDtcs(
  status?: DiagnosticStatus,
): Promise<DiagnosticTroubleCode[]> {
  const suffix = status === undefined ? "" : `?status=${status}`;
  return parseDiagnosticDtcs(await getJson(`/api/v1/diagnostics/dtcs${suffix}`));
}

export async function fetchDiagnosticDtc(code: string): Promise<DiagnosticTroubleCode> {
  return parseDiagnosticDtc(
    await getJson(`/api/v1/diagnostics/dtcs/${encodeURIComponent(code)}`),
  );
}

export async function fetchDiagnosticEvents(limit = 200): Promise<DiagnosticEvent[]> {
  return parseDiagnosticEvents(await getJson(`/api/v1/diagnostics/events?limit=${limit}`));
}

export async function fetchDiagnosticFreezeFrame(
  code: string,
): Promise<DiagnosticFreezeFrame> {
  return parseDiagnosticFreezeFrame(
    await getJson(`/api/v1/diagnostics/dtcs/${encodeURIComponent(code)}/freeze-frame`),
  );
}

export async function clearDiagnosticDtc(code: string): Promise<DiagnosticTroubleCode> {
  return parseDiagnosticDtc(
    await postJson(`/api/v1/diagnostics/dtcs/${encodeURIComponent(code)}/clear`),
  );
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

export interface InvestigationQuery {
  centerMicroseconds?: number;
  beforeMicroseconds?: number;
  afterMicroseconds?: number;
  signals?: string[];
  diagnosticCode?: string;
  baselineSessionId?: string;
  baselineCenterMicroseconds?: number;
}

function investigationParameters(query: InvestigationQuery): URLSearchParams {
  const parameters = new URLSearchParams();
  if (query.centerMicroseconds !== undefined) {
    parameters.set("center_us", String(query.centerMicroseconds));
  }
  if (query.beforeMicroseconds !== undefined) {
    parameters.set("before_us", String(query.beforeMicroseconds));
  }
  if (query.afterMicroseconds !== undefined) {
    parameters.set("after_us", String(query.afterMicroseconds));
  }
  for (const signal of query.signals ?? []) parameters.append("signal", signal);
  if (query.diagnosticCode !== undefined) parameters.set("code", query.diagnosticCode);
  if (query.baselineSessionId !== undefined) {
    parameters.set("baseline_session_id", query.baselineSessionId);
  }
  if (query.baselineCenterMicroseconds !== undefined) {
    parameters.set("baseline_center_us", String(query.baselineCenterMicroseconds));
  }
  return parameters;
}

function investigationPath(sessionId: string, suffix: string, query: InvestigationQuery): string {
  const parameters = investigationParameters(query);
  const queryString = parameters.size === 0 ? "" : `?${parameters.toString()}`;
  return `/api/v1/sessions/${encodeURIComponent(sessionId)}/investigation${suffix}${queryString}`;
}

export async function fetchInvestigation(
  sessionId: string,
  query: InvestigationQuery,
): Promise<InvestigationResult> {
  return parseInvestigation(await getJson(investigationPath(sessionId, "", query)));
}

export async function fetchInvestigationComparison(
  sessionId: string,
  query: InvestigationQuery,
): Promise<InvestigationComparison> {
  return parseInvestigationComparison(
    await getJson(investigationPath(sessionId, "/compare", query)),
  );
}

export function investigationExportUrl(
  sessionId: string,
  query: InvestigationQuery,
): string {
  return `${TUNEROS_API_URL}${investigationPath(sessionId, "/export", query)}`;
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
