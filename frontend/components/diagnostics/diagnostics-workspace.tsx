"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  clearDiagnosticDtc,
  fetchDiagnosticDtcs,
  fetchDiagnosticEvents,
  fetchDiagnosticFreezeFrame,
  fetchDiagnosticSummary,
  TelemetryApiError,
} from "../../lib/api/client";
import type {
  DiagnosticEvent,
  DiagnosticFreezeFrame,
  DiagnosticStatus,
  DiagnosticSummary,
  DiagnosticTroubleCode,
} from "../../lib/api/types";
import {
  formatDiagnosticTime,
  formatDiagnosticValue,
} from "../../lib/diagnostics/format";
import {
  canClearDiagnostic,
  filterDiagnosticDtcs,
  formatDiagnosticEvent,
  formatDiagnosticStatus,
  selectedDiagnostic,
} from "../../lib/diagnostics/state";

const REFRESH_INTERVAL_MILLISECONDS = 1_000;

export function DiagnosticsWorkspace() {
  const [summary, setSummary] = useState<DiagnosticSummary | null>(null);
  const [dtcs, setDtcs] = useState<DiagnosticTroubleCode[]>([]);
  const [events, setEvents] = useState<DiagnosticEvent[]>([]);
  const [freezeFrame, setFreezeFrame] = useState<DiagnosticFreezeFrame | null>(null);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<DiagnosticStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [nextSummary, nextDtcs, nextEvents] = await Promise.all([
      fetchDiagnosticSummary(),
      fetchDiagnosticDtcs(),
      fetchDiagnosticEvents(),
    ]);
    setSummary(nextSummary);
    setDtcs(nextDtcs);
    setEvents(nextEvents);
    setError(null);
  }, []);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        await refresh();
      } catch (reason: unknown) {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Diagnostics are unavailable");
        }
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    const interval = window.setInterval(() => void load(), REFRESH_INTERVAL_MILLISECONDS);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [refresh]);

  const filteredDtcs = useMemo(
    () => filterDiagnosticDtcs(dtcs, statusFilter),
    [dtcs, statusFilter],
  );
  const selected = selectedDiagnostic(dtcs, selectedCode);
  const selectedFreezeCode = selected?.definition.code ?? null;
  const selectedHasFreezeFrame = selected?.freeze_frame_available ?? false;

  useEffect(() => {
    let active = true;
    if (selectedFreezeCode === null || !selectedHasFreezeFrame) {
      return () => {
        active = false;
      };
    }
    fetchDiagnosticFreezeFrame(selectedFreezeCode)
      .then((frame) => {
        if (active) setFreezeFrame(frame);
      })
      .catch((reason: unknown) => {
        if (active) {
          setFreezeFrame(null);
          setError(reason instanceof Error ? reason.message : "Freeze frame is unavailable");
        }
      });
    return () => {
      active = false;
    };
  }, [selectedFreezeCode, selectedHasFreezeFrame]);

  const clearSelected = async () => {
    if (selected === null || !canClearDiagnostic(selected)) return;
    setClearing(true);
    try {
      await clearDiagnosticDtc(selected.definition.code);
      await refresh();
    } catch (reason: unknown) {
      const message =
        reason instanceof TelemetryApiError && reason.status === 409
          ? "An active or pending condition cannot be cleared."
          : reason instanceof Error
            ? reason.message
            : "DTC could not be cleared";
      setError(message);
    } finally {
      setClearing(false);
    }
  };

  if (loading && summary === null) {
    return <div className="diagnostic-empty">Loading deterministic diagnostic state…</div>;
  }

  return (
    <div className="diagnostics-workspace">
      <DiagnosticSummaryStrip summary={summary} />
      {error === null ? null : <p className="diagnostic-error" role="alert">{error}</p>}

      <section className="diagnostic-panel">
        <div className="diagnostic-heading">
          <div><span className="section-kicker">Synthetic TunerOS rules</span><h2>Diagnostic trouble codes</h2></div>
          <label>Status filter
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as DiagnosticStatus | "all")}>
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="pending">Pending</option>
              <option value="historical">Historical</option>
              <option value="cleared">Cleared</option>
            </select>
          </label>
        </div>
        {dtcs.length === 0 ? (
          <div className="diagnostic-empty"><strong>No diagnostic trouble codes</strong><span>No configured rule has entered a DTC lifecycle state.</span></div>
        ) : (
          <div className="diagnostic-table-scroll">
            <table className="diagnostic-table">
              <thead><tr><th>Code</th><th>Name</th><th>System</th><th>Severity</th><th>Status</th><th>First detected</th><th>Last seen</th><th>Occurrences</th></tr></thead>
              <tbody>{filteredDtcs.map((dtc) => (
                <tr key={dtc.definition.code} className={selected?.definition.code === dtc.definition.code ? "selected" : ""} onClick={() => setSelectedCode(dtc.definition.code)}>
                  <td className="mono diagnostic-code">{dtc.definition.code}</td>
                  <td>{dtc.definition.name}</td><td>{dtc.definition.source_system}</td>
                  <td>{formatDiagnosticStatus(dtc.definition.severity)}</td>
                  <td><span className={`diagnostic-status ${dtc.status}`}>{formatDiagnosticStatus(dtc.status)}</span></td>
                  <td className="mono">{formatDiagnosticTime(dtc.first_detected_timestamp_microseconds)}</td>
                  <td className="mono">{formatDiagnosticTime(dtc.last_seen_timestamp_microseconds)}</td>
                  <td className="mono">{dtc.occurrence_count}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>

      <div className="diagnostic-investigation-grid">
        <DiagnosticDetail dtc={selected} clearing={clearing} onClear={() => void clearSelected()} />
        <DiagnosticTimeline events={events} />
      </div>
      <FreezeFramePanel
        frame={freezeFrame?.code === selectedFreezeCode ? freezeFrame : null}
        expected={selectedHasFreezeFrame}
      />
    </div>
  );
}

function DiagnosticSummaryStrip({ summary }: Readonly<{ summary: DiagnosticSummary | null }>) {
  return <section className="diagnostic-summary" aria-label="Diagnostic summary">
    <div><span className={`source-mode ${summary?.source.mode ?? "live"}`}>{summary?.source.mode ?? "live"}</span><strong>{summary?.source.session_name ?? "Active telemetry source"}</strong><small>{summary?.service_state ?? "unavailable"} · deterministic telemetry analysis</small></div>
    <dl>
      <div><dt>Pending</dt><dd>{summary?.pending_count ?? 0}</dd></div>
      <div><dt>Active</dt><dd>{summary?.active_count ?? 0}</dd></div>
      <div><dt>Historical</dt><dd>{summary?.historical_count ?? 0}</dd></div>
      <div><dt>Cleared</dt><dd>{summary?.cleared_count ?? 0}</dd></div>
      <div><dt>Latest sim time</dt><dd className="mono">{formatDiagnosticTime(summary?.observation_timestamp_microseconds ?? null)}</dd></div>
    </dl>
  </section>;
}

function DiagnosticDetail({ dtc, clearing, onClear }: Readonly<{ dtc: DiagnosticTroubleCode | null; clearing: boolean; onClear: () => void }>) {
  if (dtc === null) return <section className="diagnostic-detail"><p>Select a DTC when diagnostic history exists.</p></section>;
  return <section className="diagnostic-detail">
    <span className={`diagnostic-status ${dtc.status}`}>{formatDiagnosticStatus(dtc.status)}</span>
    <h2 className="mono">{dtc.definition.code}</h2><h3>{dtc.definition.name}</h3><p>{dtc.definition.description}</p>
    <dl>
      <div><dt>Rule</dt><dd className="mono">{dtc.definition.rule_id}</dd></div><div><dt>System</dt><dd>{dtc.definition.source_system}</dd></div>
      <div><dt>Severity</dt><dd>{formatDiagnosticStatus(dtc.definition.severity)}</dd></div><div><dt>Occurrences</dt><dd>{dtc.occurrence_count}</dd></div>
      <div><dt>Confirmed</dt><dd className="mono">{formatDiagnosticTime(dtc.confirmed_timestamp_microseconds)}</dd></div><div><dt>Resolved</dt><dd className="mono">{formatDiagnosticTime(dtc.resolved_timestamp_microseconds)}</dd></div>
      <div><dt>Cleared</dt><dd className="mono">{formatDiagnosticTime(dtc.cleared_timestamp_microseconds)}</dd></div><div><dt>Freeze frame</dt><dd>{dtc.freeze_frame_available ? "Available" : "Not captured"}</dd></div>
    </dl>
    <div className="diagnostic-rule"><span>Activate</span><code>{dtc.definition.activation_description}</code><span>Recover</span><code>{dtc.definition.recovery_description}</code></div>
    <button className="diagnostic-clear" type="button" disabled={!canClearDiagnostic(dtc) || clearing} onClick={onClear}>{clearing ? "Clearing…" : "Clear historical DTC"}</button>
    {dtc.status === "active" ? <small>Active conditions cannot be cleared.</small> : null}
  </section>;
}

function DiagnosticTimeline({ events }: Readonly<{ events: DiagnosticEvent[] }>) {
  return <section className="diagnostic-timeline"><div className="diagnostic-heading"><div><span className="section-kicker">Bounded transition history</span><h2>Event timeline</h2></div></div>
    {events.length === 0 ? <p className="diagnostic-empty">No diagnostic transitions</p> : <ol>{events.toReversed().map((event) => <li key={event.sequence}><span className="mono">#{event.sequence}</span><div><strong>{formatDiagnosticEvent(event)}</strong><small>{event.code} · {formatDiagnosticTime(event.timestamp_microseconds)}</small></div></li>)}</ol>}
  </section>;
}

function FreezeFramePanel({ frame, expected }: Readonly<{ frame: DiagnosticFreezeFrame | null; expected: boolean }>) {
  return <section className="diagnostic-panel freeze-frame-panel"><div className="diagnostic-heading"><div><span className="section-kicker">Immutable activation evidence</span><h2>Freeze frame</h2></div><span>{frame === null ? (expected ? "Loading…" : "Not captured") : `Captured at ${formatDiagnosticTime(frame.capture_timestamp_microseconds)}`}</span></div>
    {frame === null ? <p className="diagnostic-empty">No activation freeze frame is available for the selected DTC.</p> : <div className="diagnostic-table-scroll"><table className="diagnostic-table"><thead><tr><th>Signal</th><th>Value</th><th>Unit</th><th>Source</th><th>Message</th><th>Signal timestamp</th></tr></thead><tbody>{frame.signals.map((signal) => <tr key={`${signal.key.message_name}.${signal.key.signal_name}`}><td>{signal.key.signal_name}</td><td className="mono">{formatDiagnosticValue(signal.value)}</td><td>{signal.unit}</td><td>{signal.source_ecu}</td><td>{signal.key.message_name}</td><td className="mono">{formatDiagnosticTime(signal.timestamp_microseconds)}</td></tr>)}</tbody></table></div>}
  </section>;
}
