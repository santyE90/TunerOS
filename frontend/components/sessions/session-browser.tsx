"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchSessionDetail, fetchSessions } from "../../lib/api/client";
import type { SessionDetail, SessionSummary } from "../../lib/api/types";
import {
  formatFrameCount,
  formatSessionDuration,
  sessionDisplayName,
} from "../../lib/sessions/format";
import { useTelemetry, useTelemetryActions } from "../telemetry/telemetry-provider";

export function SessionBrowser() {
  const router = useRouter();
  const telemetry = useTelemetry();
  const { replaySession } = useTelemetryActions();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selected, setSelected] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replaying, setReplaying] = useState(false);

  useEffect(() => {
    let active = true;
    fetchSessions()
      .then(async (items) => {
        if (!active) return;
        setSessions(items);
        if (items.length > 0) {
          const detail = await fetchSessionDetail(items[0].session_id);
          if (active) setSelected(detail);
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Sessions are unavailable");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const selectSession = async (session: SessionSummary) => {
    setError(null);
    try {
      setSelected(await fetchSessionDetail(session.session_id));
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Session detail is unavailable");
    }
  };

  const startReplay = async () => {
    if (selected === null) return;
    setReplaying(true);
    setError(null);
    try {
      await replaySession(selected.session_id);
      router.push("/");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Session replay could not start");
      setReplaying(false);
    }
  };

  if (loading) {
    return <div className="session-empty">Loading the local session catalog…</div>;
  }
  if (sessions.length === 0) {
    return (
      <div className="session-empty">
        <span className="section-kicker">No recorded sessions</span>
        <h2>Session catalog is empty</h2>
        <p>
          Launch the local API with <code>--record-session</code> while consuming an existing CAN
          gateway run. TunerOS does not record automatically.
        </p>
        {error === null ? null : <strong role="alert">{error}</strong>}
      </div>
    );
  }

  return (
    <div className="session-browser">
      <section className="session-list" aria-label="Complete recorded sessions">
        {sessions.map((session) => (
          <button
            type="button"
            className={selected?.session_id === session.session_id ? "session-row selected" : "session-row"}
            onClick={() => void selectSession(session)}
            key={session.session_id}
          >
            <span>
              <strong>{sessionDisplayName(session)}</strong>
              <small className="mono">{session.session_id.slice(0, 8)}</small>
            </span>
            <span>
              <strong>{formatFrameCount(session.frame_count)}</strong>
              <small>frames</small>
            </span>
            <span>
              <strong>{formatSessionDuration(session.duration_microseconds)}</strong>
              <small>{session.scenario ?? "scenario not supplied"}</small>
            </span>
            <span className={`compatibility ${session.dbc_compatible ? "compatible" : "mismatch"}`}>
              {session.dbc_compatible ? "DBC MATCH" : "DBC MISMATCH"}
            </span>
          </button>
        ))}
      </section>

      <aside className="session-detail-panel">
        {selected === null ? (
          <p>Select a session to inspect its immutable capture metadata.</p>
        ) : (
          <>
            <span className="section-kicker">Raw CAN artifact</span>
            <h2>{sessionDisplayName(selected)}</h2>
            <p className="session-id mono">{selected.session_id}</p>
            <dl className="session-detail-list">
              <div><dt>Status</dt><dd>{selected.status}</dd></div>
              <div><dt>Created UTC</dt><dd>{selected.created_at_utc}</dd></div>
              <div><dt>Scenario</dt><dd>{selected.scenario ?? "Not supplied"}</dd></div>
              <div><dt>Frames</dt><dd>{formatFrameCount(selected.frame_count)}</dd></div>
              <div><dt>Duration</dt><dd>{formatSessionDuration(selected.duration_microseconds)}</dd></div>
              <div><dt>First timestamp</dt><dd>{selected.first_timestamp_microseconds ?? "—"} µs</dd></div>
              <div><dt>Last timestamp</dt><dd>{selected.last_timestamp_microseconds ?? "—"} µs</dd></div>
              <div><dt>Vehicle profile</dt><dd>{selected.vehicle_profile_id}</dd></div>
              <div><dt>Network</dt><dd>{selected.can_network}</dd></div>
              <div><dt>DBC</dt><dd>{selected.dbc_name}</dd></div>
              <div><dt>Format</dt><dd>v{selected.format_version}</dd></div>
            </dl>
            <div className="hash-block">
              <span>DBC SHA-256</span><code>{selected.dbc_sha256}</code>
              <span>Frames SHA-256</span><code>{selected.frames_sha256}</code>
            </div>
            <button
              type="button"
              className="replay-button"
              disabled={
                replaying ||
                !selected.dbc_compatible ||
                telemetry.serviceState === "running" ||
                telemetry.serviceState === "connecting"
              }
              onClick={() => void startReplay()}
            >
              {replaying ? "Starting replay…" : "Replay session"}
            </button>
            <button
              type="button"
              className="investigate-button"
              disabled={!selected.dbc_compatible}
              onClick={() => router.push(`/sessions/${selected.session_id}/investigate`)}
            >
              Investigate session
            </button>
            <p className="replay-note">
              Replay feeds the active source. Investigation performs isolated bounded analysis.
            </p>
            {error === null ? null : <p className="session-error" role="alert">{error}</p>}
          </>
        )}
      </aside>
    </div>
  );
}
