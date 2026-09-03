"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, type MouseEvent, useEffect, useMemo, useState } from "react";

import {
  fetchInvestigation,
  fetchInvestigationComparison,
  fetchSessions,
  investigationExportUrl,
  type InvestigationQuery,
} from "../../lib/api/client";
import type {
  CanExplorerFrame,
  InvestigationComparison,
  InvestigationResult,
  InvestigationSignalSeries,
  SessionSummary,
  SignalSample,
  SignalValue,
} from "../../lib/api/types";
import {
  displayCanPayload,
  formatCanMessageName,
  formatCanTimestamp,
} from "../../lib/can/format";
import { formatDiagnosticEvent, formatDiagnosticStatus } from "../../lib/diagnostics/state";
import {
  canonicalSignal,
  latestAtOrBefore,
  parseInvestigationUrl,
  RAW_CURSOR_RADIUS_MICROSECONDS,
  relativeTimestampMicroseconds,
  toggleInvestigationSignal,
} from "../../lib/investigation/state";
import { formatSessionDuration, sessionDisplayName } from "../../lib/sessions/format";

export function InvestigationWorkspace() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = params.sessionId;
  const parsed = useMemo(() => {
    try {
      return { state: parseInvestigationUrl(new URLSearchParams(searchParams.toString())), error: null };
    } catch (reason: unknown) {
      return {
        state: null,
        error: reason instanceof Error ? reason.message : "Invalid investigation URL",
      };
    }
  }, [searchParams]);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [comparison, setComparison] = useState<InvestigationComparison | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [selectedFrameSequence, setSelectedFrameSequence] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(parsed.error);

  const query = useMemo<InvestigationQuery | null>(() => {
    if (parsed.state === null) return null;
    return {
      centerMicroseconds: parsed.state.centerMicroseconds,
      beforeMicroseconds: parsed.state.beforeMicroseconds,
      afterMicroseconds: parsed.state.afterMicroseconds,
      signals: parsed.state.signals.length === 0 ? undefined : parsed.state.signals,
      diagnosticCode: parsed.state.diagnosticCode,
      baselineSessionId: parsed.state.baselineSessionId,
      baselineCenterMicroseconds: parsed.state.baselineCenterMicroseconds,
    };
  }, [parsed.state]);

  useEffect(() => {
    let active = true;
    fetchSessions().then((items) => {
      if (active) setSessions(items);
    }).catch(() => {
      if (active) setSessions([]);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    if (query === null) return () => { active = false; };
    const request = query.baselineSessionId === undefined
      ? fetchInvestigation(sessionId, query).then((next) => ({ primary: next, comparison: null }))
      : fetchInvestigationComparison(sessionId, query).then((next) => ({
          primary: next.primary,
          comparison: next,
        }));
    request.then((next) => {
      if (!active) return;
      setResult(next.primary);
      setComparison(next.comparison);
      setError(null);
      setCursor(next.primary.window.center_timestamp_microseconds);
      setSelectedFrameSequence(null);
      if (parsed.state?.centerMicroseconds === undefined) {
        const canonical = new URLSearchParams(searchParams.toString());
        canonical.set("t", String(next.primary.window.center_timestamp_microseconds));
        router.replace(
          `/sessions/${encodeURIComponent(sessionId)}/investigate?${canonical.toString()}`,
        );
      }
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : "Investigation failed");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [parsed.state?.centerMicroseconds, query, router, searchParams, sessionId]);

  const replaceQuery = (changes: Record<string, string | string[] | undefined>) => {
    const next = new URLSearchParams(searchParams.toString());
    for (const [name, value] of Object.entries(changes)) {
      next.delete(name);
      if (Array.isArray(value)) value.forEach((item) => next.append(name, item));
      else if (value !== undefined && value !== "") next.set(name, value);
    }
    router.replace(`/sessions/${encodeURIComponent(sessionId)}/investigate?${next.toString()}`);
  };

  const applyWindow = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    replaceQuery({
      t: String(data.get("center") ?? ""),
      before: String(data.get("before") ?? ""),
      after: String(data.get("after") ?? ""),
      baseline_t: String(data.get("baselineCenter") ?? "") || undefined,
    });
  };

  if (parsed.error !== null) return <p className="investigation-error">{parsed.error}</p>;
  if (loading && result === null) return <div className="investigation-empty">Scanning validated raw session evidence…</div>;
  if (result === null) return <div className="investigation-empty"><strong>Investigation unavailable</strong><span>{error}</span></div>;

  const selectedNames = result.selected_signals.map(canonicalSignal);
  const activeCursor = cursor ?? result.window.center_timestamp_microseconds;
  const nearbyFrames = result.raw_frames.filter(
    (frame) => Math.abs(frame.timestamp_microseconds - activeCursor) <= RAW_CURSOR_RADIUS_MICROSECONDS,
  );
  const selectedFrame = result.raw_frames.find((frame) => frame.sequence === selectedFrameSequence)
    ?? nearbyFrames[0];
  const exportQuery: InvestigationQuery = {
    ...(query ?? {}),
    centerMicroseconds: result.window.center_timestamp_microseconds,
    signals: selectedNames,
  };

  return (
    <div className="investigation-workspace">
      <section className="investigation-source">
        <div><span className="section-kicker">Recorded session · isolated analysis</span><h2>{sessionDisplayName(result.session)}</h2><code>{result.session.session_id}</code></div>
        <dl>
          <div><dt>Scenario</dt><dd>{result.session.scenario ?? "Not supplied"}</dd></div>
          <div><dt>Frames</dt><dd>{result.session.frame_count.toLocaleString("en-US")}</dd></div>
          <div><dt>Duration</dt><dd>{formatSessionDuration(result.session.duration_microseconds)}</dd></div>
          <div><dt>Vehicle</dt><dd>{result.session.vehicle_profile_id}</dd></div>
          <div><dt>DBC</dt><dd>{result.session.dbc_compatible ? "MATCH" : "MISMATCH"}</dd></div>
        </dl>
      </section>

      <form className="investigation-controls" onSubmit={applyWindow}>
        <label>Center µs<input name="center" type="number" min="0" defaultValue={result.window.center_timestamp_microseconds} /></label>
        <label>Before µs<input name="before" type="number" min="0" defaultValue={result.window.requested_before_microseconds} /></label>
        <label>After µs<input name="after" type="number" min="0" defaultValue={result.window.requested_after_microseconds} /></label>
        <label>Healthy baseline<select value={parsed.state?.baselineSessionId ?? ""} onChange={(event) => replaceQuery({ baseline: event.target.value || undefined })}><option value="">None</option>{sessions.filter((item) => item.session_id !== sessionId && item.dbc_compatible).map((item) => <option key={item.session_id} value={item.session_id}>{sessionDisplayName(item)}</option>)}</select></label>
        <label>Baseline center µs<input name="baselineCenter" type="number" min="0" defaultValue={comparison?.baseline.window.center_timestamp_microseconds ?? parsed.state?.baselineCenterMicroseconds ?? result.window.center_timestamp_microseconds} /></label>
        <button type="submit">Apply window</button>
        <a className="evidence-export" href={investigationExportUrl(sessionId, exportQuery)} download>Export Evidence</a>
      </form>
      {error === null ? null : <p className="investigation-error" role="alert">{error}</p>}
      {comparison === null ? null : <section className="comparison-identities"><div><span>PRIMARY</span><strong>{sessionDisplayName(comparison.primary.session)}</strong><small className="mono">center {comparison.primary.window.center_timestamp_microseconds} µs · actual {comparison.primary.window.start_timestamp_microseconds}–{comparison.primary.window.end_timestamp_microseconds} µs</small></div><div><span>BASELINE</span><strong>{sessionDisplayName(comparison.baseline.session)}</strong><small className="mono">center {comparison.baseline.window.center_timestamp_microseconds} µs · actual {comparison.baseline.window.start_timestamp_microseconds}–{comparison.baseline.window.end_timestamp_microseconds} µs</small></div></section>}

      <InvestigationTimeline result={result} cursor={activeCursor} onCursor={setCursor} />

      <div className="investigation-context-grid">
        <DiagnosticContext result={result} />
        <FreezeContext result={result} />
      </div>

      <section className="investigation-panel">
        <div className="investigation-heading"><div><span className="section-kicker">Canonical DBC catalog</span><h2>Telemetry evidence</h2></div><span>{selectedNames.length} / 6 signals</span></div>
        <div className="investigation-signal-picker">
          {result.available_signals.map((definition) => {
            const name = canonicalSignal(definition.key);
            return <label key={name}><input type="checkbox" checked={selectedNames.includes(name)} onChange={() => {
              try { replaceQuery({ signal: toggleInvestigationSignal(selectedNames, name) }); }
              catch (reason: unknown) { setError(reason instanceof Error ? reason.message : "Signal selection failed"); }
            }} />{definition.key.signal_name}<small>{definition.message_name}</small></label>;
          })}
        </div>
        <div className="investigation-charts">
          {result.telemetry_series.map((series) => <EvidenceChart key={canonicalSignal(series.definition.key)} series={series} baseline={comparison?.baseline.telemetry_series.find((item) => canonicalSignal(item.definition.key) === canonicalSignal(series.definition.key))} result={result} baselineResult={comparison?.baseline} cursor={activeCursor} onCursor={setCursor} />)}
        </div>
        <CursorValues result={result} baseline={comparison?.baseline ?? null} cursor={activeCursor} />
        {comparison === null ? null : <ComparisonSummary comparison={comparison} />}
      </section>

      <section className="investigation-panel">
        <div className="investigation-heading"><div><span className="section-kicker">±100 ms around cursor</span><h2>Raw CAN evidence</h2></div><span>{nearbyFrames.length} nearby · {result.statistics.raw_frame_count.toLocaleString("en-US")} in window</span></div>
        <div className="investigation-raw-layout">
          <div className="can-table-scroll"><table className="can-table"><thead><tr><th>Session seq</th><th>Time</th><th>CAN ID</th><th>Message</th><th>Source</th><th>DLC</th><th>Payload</th></tr></thead><tbody>{nearbyFrames.map((frame) => <tr key={frame.sequence} className={selectedFrame?.sequence === frame.sequence ? "selected" : ""} onClick={() => setSelectedFrameSequence(frame.sequence)}><td className="mono">{frame.sequence}</td><td className="mono">{formatCanTimestamp(frame.timestamp_microseconds)}</td><td className="mono">{frame.arbitration_id_hex}</td><td>{formatCanMessageName(frame.message_name)}</td><td>{frame.source_ecu ?? "—"}</td><td>{frame.dlc}</td><td className="mono">{displayCanPayload(frame.payload_hex)}</td></tr>)}</tbody></table></div>
          <InvestigationFrameDetail frame={selectedFrame} />
        </div>
      </section>
    </div>
  );
}

function InvestigationTimeline({ result, cursor, onCursor }: Readonly<{ result: InvestigationResult; cursor: number; onCursor: (value: number) => void }>) {
  const window = result.window;
  const span = Math.max(1, window.end_timestamp_microseconds - window.start_timestamp_microseconds);
  const position = (timestamp: number) => ((timestamp - window.start_timestamp_microseconds) / span) * 100;
  return <section className="investigation-timeline"><div className="investigation-heading"><div><span className="section-kicker">Simulation-time correlation</span><h2>Investigation timeline</h2></div><span>{formatCanTimestamp(window.start_timestamp_microseconds)} → {formatCanTimestamp(window.end_timestamp_microseconds)}</span></div><div className="timeline-track"><span className="timeline-center" style={{ left: `${position(window.center_timestamp_microseconds)}%` }} title="Investigation center" />{result.diagnostic_events.map((event) => <span className="timeline-event" key={event.sequence} style={{ left: `${position(event.timestamp_microseconds)}%` }} title={`${event.code} ${event.event_type}`} />)}{result.freeze_frames_at_center.map((frame) => <span className="timeline-freeze" key={frame.code} style={{ left: `${position(frame.capture_timestamp_microseconds)}%` }} title={`${frame.code} freeze frame`} />)}<span className="timeline-cursor" style={{ left: `${position(cursor)}%` }} /></div><input aria-label="Investigation cursor" type="range" min={window.start_timestamp_microseconds} max={window.end_timestamp_microseconds} step="10000" value={cursor} onChange={(event) => onCursor(Number(event.target.value))} /><div className="timeline-legend"><span>Center</span><span>Diagnostic event</span><span>Freeze frame</span><strong className="mono">Cursor {cursor} µs</strong></div></section>;
}

function DiagnosticContext({ result }: Readonly<{ result: InvestigationResult }>) {
  const relevant = result.diagnostic_states_at_center.filter((item) => item.status !== "absent");
  return <section className="investigation-panel"><span className="section-kicker">State at center</span><h2>Diagnostic context</h2>{relevant.length === 0 ? <p className="investigation-empty">No DTC state at this timestamp.</p> : relevant.map((item) => <div className="investigation-dtc" key={item.definition.code}><span className={`diagnostic-status ${item.status}`}>{item.status === "absent" ? "Absent" : formatDiagnosticStatus(item.status)}</span><strong className="mono">{item.definition.code}</strong><p>{item.definition.name}</p></div>)}<ol className="investigation-events">{result.diagnostic_events.map((event) => <li key={event.sequence}><code>#{event.sequence}</code><span>{formatDiagnosticEvent(event)}</span><small>{event.timestamp_microseconds} µs</small></li>)}</ol></section>;
}

function FreezeContext({ result }: Readonly<{ result: InvestigationResult }>) {
  const frame = result.freeze_frames_at_center[0];
  return <section className="investigation-panel"><span className="section-kicker">Immutable Phase 7A evidence</span><h2>Freeze frame</h2>{frame === undefined ? <p className="investigation-empty">No freeze frame existed at the center timestamp.</p> : <><strong className="mono">{frame.code} · {frame.capture_timestamp_microseconds} µs</strong><div className="freeze-mini-grid">{frame.signals.map((signal) => <div key={canonicalSignal(signal.key)}><span>{signal.key.signal_name}</span><strong>{String(signal.value)} {signal.unit}</strong><small>{signal.source_ecu}</small></div>)}</div></>}</section>;
}

function EvidenceChart({ series, baseline, result, baselineResult, cursor, onCursor }: Readonly<{ series: InvestigationSignalSeries; baseline?: InvestigationSignalSeries; result: InvestigationResult; baselineResult?: InvestigationResult; cursor: number; onCursor: (value: number) => void }>) {
  const allSamples = [...series.samples, ...(baseline?.samples ?? [])];
  const numeric = allSamples.filter((sample) => typeof sample.value === "number");
  const values = numeric.map((sample) => Number(sample.value));
  const minimum = values.length === 0 ? 0 : Math.min(...values);
  const maximum = values.length === 0 ? 1 : Math.max(...values);
  const valueSpan = Math.max(maximum - minimum, 1e-9);
  const totalSpan = Math.max(1, result.window.requested_before_microseconds + result.window.requested_after_microseconds);
  const x = (timestamp: number, center: number) => ((relativeTimestampMicroseconds(timestamp, center) + result.window.requested_before_microseconds) / totalSpan) * 100;
  const y = (value: SignalValue) => typeof value === "boolean" ? (value ? 15 : 85) : 85 - ((Number(value) - minimum) / valueSpan) * 70;
  const points = (item: InvestigationSignalSeries, center: number) => item.samples.map((sample) => `${x(sample.timestamp_microseconds, center)},${y(sample.value)}`).join(" ");
  const click = (event: MouseEvent<SVGSVGElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width));
    const requested = result.window.center_timestamp_microseconds - result.window.requested_before_microseconds + ratio * totalSpan;
    onCursor(Math.round(Math.min(result.window.end_timestamp_microseconds, Math.max(result.window.start_timestamp_microseconds, requested))));
  };
  const context = result.start_context.find((sample) => canonicalSignal(sample.key) === canonicalSignal(series.definition.key));
  const current = latestAtOrBefore(series, context, cursor);
  return <article className="evidence-chart"><header><div><strong>{series.definition.key.signal_name}</strong><small>{series.definition.source_ecu} · {series.definition.unit}</small></div><span className="mono">{current === undefined ? "—" : String(current.value)}</span></header><svg viewBox="0 0 100 100" preserveAspectRatio="none" onClick={click} role="img" aria-label={`${series.definition.key.signal_name} evidence plot`}><line x1="0" y1="85" x2="100" y2="85" /><polyline className="primary-series" points={points(series, result.window.center_timestamp_microseconds)} />{baseline === undefined || baselineResult === undefined ? null : <polyline className="baseline-series" points={points(baseline, baselineResult.window.center_timestamp_microseconds)} />}<line className="chart-cursor" x1={x(cursor, result.window.center_timestamp_microseconds)} y1="0" x2={x(cursor, result.window.center_timestamp_microseconds)} y2="100" /></svg><footer><span>PRIMARY</span>{baseline === undefined ? null : <span>BASELINE</span>}<span>{series.samples.length} observations</span></footer></article>;
}

function CursorValues({ result, baseline, cursor }: Readonly<{ result: InvestigationResult; baseline: InvestigationResult | null; cursor: number }>) {
  return <div className="cursor-values"><div className="investigation-heading"><div><span className="section-kicker">No interpolation</span><h3>Latest observations at or before cursor</h3></div></div><table><thead><tr><th>Signal</th><th>Primary</th><th>Baseline</th><th>Unit</th><th>Observed at</th></tr></thead><tbody>{result.telemetry_series.map((series) => {
    const name = canonicalSignal(series.definition.key);
    const context = result.start_context.find((sample) => canonicalSignal(sample.key) === name);
    const primary = latestAtOrBefore(series, context, cursor);
    const baselineSeries = baseline?.telemetry_series.find((item) => canonicalSignal(item.definition.key) === name);
    const baselineContext = baseline?.start_context.find((sample) => canonicalSignal(sample.key) === name);
    const relative = cursor - result.window.center_timestamp_microseconds;
    const baselineCursor = baseline === null ? 0 : baseline.window.center_timestamp_microseconds + relative;
    const baselineSample = baselineSeries === undefined ? undefined : latestAtOrBefore(baselineSeries, baselineContext, baselineCursor);
    return <tr key={name}><td>{series.definition.key.signal_name}</td><td className="mono">{sampleValue(primary)}</td><td className="mono">{sampleValue(baselineSample)}</td><td>{series.definition.unit}</td><td className="mono">{primary?.timestamp_microseconds ?? "—"}</td></tr>;
  })}</tbody></table></div>;
}

function sampleValue(sample: SignalSample | undefined): string { return sample === undefined ? "—" : String(sample.value); }

function ComparisonSummary({ comparison }: Readonly<{ comparison: InvestigationComparison }>) {
  return <div className="comparison-summary"><div className="investigation-heading"><div><span className="section-kicker">Relative-center alignment</span><h3>Primary / healthy baseline statistics</h3></div><span>No causality or anomaly score implied</span></div>{comparison.diagnostic_code === null ? <p className="comparison-diagnostic-note">No diagnostic code selected for event comparison.</p> : <div className="comparison-diagnostic-note"><span><code>{comparison.diagnostic_code}</code> event in primary window: {comparison.primary_has_diagnostic_event ? "yes" : "no"}</span><span>event in baseline window: {comparison.baseline_has_diagnostic_event ? "yes" : "no"}</span></div>}<table><thead><tr><th>Signal</th><th>Primary min / mean / max</th><th>Baseline min / mean / max</th><th>Mean Δ</th><th>Count P / B</th></tr></thead><tbody>{comparison.signal_comparisons.map((item) => <tr key={canonicalSignal(item.key)}><td>{item.key.signal_name}</td><td className="mono">{summaryValues(item.primary)}</td><td className="mono">{summaryValues(item.baseline)}</td><td className="mono">{item.mean_difference?.toFixed(3) ?? "—"}</td><td>{item.primary.observation_count} / {item.baseline.observation_count}</td></tr>)}</tbody></table></div>;
}

function summaryValues(summary: InvestigationComparison["signal_comparisons"][number]["primary"]): string { return summary.mean === null ? `${String(summary.first)} → ${String(summary.last)}` : `${summary.minimum?.toFixed(2)} / ${summary.mean.toFixed(2)} / ${summary.maximum?.toFixed(2)}`; }

function InvestigationFrameDetail({ frame }: Readonly<{ frame: CanExplorerFrame | undefined }>) {
  if (frame === undefined) return <aside className="can-detail">No raw frame exists within ±100 ms of the cursor.</aside>;
  return <aside className="can-detail"><span className={`decode-badge ${frame.decode_status}`}>{frame.decode_status}</span><h3>{formatCanMessageName(frame.message_name)}</h3><dl><div><dt>Session sequence</dt><dd>{frame.sequence}</dd></div><div><dt>Timestamp</dt><dd>{frame.timestamp_microseconds} µs</dd></div><div><dt>CAN ID</dt><dd>{frame.arbitration_id_hex}</dd></div><div><dt>Source</dt><dd>{frame.source_ecu ?? "—"}</dd></div><div><dt>DLC</dt><dd>{frame.dlc}</dd></div></dl><code className="investigation-payload">{frame.payload_hex}</code><table><tbody>{frame.decoded_signals.map((signal) => <tr key={signal.signal_name}><td>{signal.signal_name}</td><td className="mono">{String(signal.value)}</td><td>{signal.unit}</td></tr>)}</tbody></table></aside>;
}
