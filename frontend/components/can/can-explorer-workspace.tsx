"use client";

import { useMemo, useState } from "react";

import type { CanExplorerFrame } from "../../lib/api/types";
import {
  displayCanPayload,
  formatCanFrequency,
  formatCanMessageName,
  formatCanTimestamp,
  formatExpectedFrequency,
} from "../../lib/can/format";
import { filterCanFrames } from "../../lib/can/state";
import { useCanExplorer, useCanExplorerActions } from "./can-explorer-provider";

const MAX_RENDERED_FRAMES = 500;

export function CanExplorerWorkspace() {
  const explorer = useCanExplorer();
  const { toggleFreeze } = useCanExplorerActions();
  const [canId, setCanId] = useState("");
  const [messageName, setMessageName] = useState("");
  const [sourceEcu, setSourceEcu] = useState("");
  const [text, setText] = useState("");
  const [followLive, setFollowLive] = useState(true);
  const [selectedSequence, setSelectedSequence] = useState<number | null>(null);

  const messages = useMemo(
    () => Object.values(explorer.messages).sort((a, b) => a.arbitration_id - b.arbitration_id),
    [explorer.messages],
  );
  const filtered = useMemo(
    () => filterCanFrames(explorer.displayedFrames, { canId, messageName, sourceEcu, text }),
    [canId, explorer.displayedFrames, messageName, sourceEcu, text],
  );
  const rendered = useMemo(() => {
    const recent = filtered.slice(-MAX_RENDERED_FRAMES);
    return followLive ? recent.toReversed() : recent;
  }, [filtered, followLive]);
  const selected =
    explorer.displayedFrames.find((frame) => frame.sequence === selectedSequence) ?? rendered[0];

  return (
    <div className="can-explorer">
      <section className="can-source-strip" aria-label="Raw CAN source status">
        <div>
          <span className={`source-mode ${explorer.source.mode}`}>{explorer.source.mode}</span>
          <strong>{explorer.source.session_name ?? "Synthetic CAN gateway"}</strong>
          <small className="mono">{explorer.source.session_id ?? "local active source"}</small>
        </div>
        <dl>
          <div><dt>Service</dt><dd>{explorer.serviceState}</dd></div>
          <div><dt>Observed</dt><dd>{explorer.statistics.total_frame_count.toLocaleString("en-US")}</dd></div>
          <div><dt>Retained</dt><dd>{explorer.statistics.retained_frame_count.toLocaleString("en-US")}</dd></div>
          <div><dt>CAN IDs</dt><dd>{explorer.statistics.unique_id_count}</dd></div>
        </dl>
        <button type="button" className={explorer.frozen ? "freeze-button active" : "freeze-button"} onClick={toggleFreeze}>
          {explorer.frozen ? "Resume View" : "Freeze View"}
        </button>
      </section>

      {explorer.framesPassedWhileFrozen > 0 ? (
        <p className="can-freeze-notice" role="status">
          View frozen · {explorer.framesPassedWhileFrozen.toLocaleString("en-US")} frames passed.
          Resume reconciles to the latest bounded buffer.
        </p>
      ) : null}
      {explorer.streamWarning === null ? null : <p className="can-warning">{explorer.streamWarning}</p>}
      {explorer.error === null ? null : <p className="can-error" role="alert">{explorer.error}</p>}

      <section className="can-message-panel">
        <div className="can-section-heading">
          <div><span className="section-kicker">Bus inventory</span><h2>Message rates</h2></div>
          <span>Simulation-time averages · no fault classification</span>
        </div>
        <div className="can-table-scroll compact">
          <table className="can-table">
            <thead><tr><th>CAN ID</th><th>Message</th><th>ECU</th><th>Retained</th><th>Total</th><th>Expected</th><th>Observed</th><th>Latest Time</th></tr></thead>
            <tbody>
              {messages.map((message) => (
                <tr key={message.arbitration_id} onClick={() => setCanId(message.arbitration_id_hex)}>
                  <td className="mono">{message.arbitration_id_hex}</td>
                  <td>{formatCanMessageName(message.message_name)}</td>
                  <td>{message.source_ecu ?? "—"}</td>
                  <td className="mono">{message.retained_frame_count.toLocaleString("en-US")}</td>
                  <td className="mono">{message.total_frame_count.toLocaleString("en-US")}</td>
                  <td className="mono">{formatExpectedFrequency(message.expected_period_microseconds)}</td>
                  <td className="mono">{formatCanFrequency(message.observed_frequency_hz)}</td>
                  <td className="mono">{formatCanTimestamp(message.latest_timestamp_microseconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="can-frame-panel">
        <div className="can-section-heading">
          <div><span className="section-kicker">Bounded observation window</span><h2>Raw frames</h2></div>
          <label className="follow-control"><input type="checkbox" checked={followLive} onChange={(event) => setFollowLive(event.target.checked)} /> Follow live</label>
        </div>
        <div className="can-filters">
          <label>CAN ID<input value={canId} onChange={(event) => setCanId(event.target.value)} placeholder="0x500" /></label>
          <label>Message<input value={messageName} onChange={(event) => setMessageName(event.target.value)} placeholder="DmeFastEngine" /></label>
          <label>ECU/source<input value={sourceEcu} onChange={(event) => setSourceEcu(event.target.value)} placeholder="TunerOsSimulatedDme" /></label>
          <label>Payload/message<input value={text} onChange={(event) => setText(event.target.value)} placeholder="70 17" /></label>
          <button type="button" onClick={() => { setCanId(""); setMessageName(""); setSourceEcu(""); setText(""); }}>Clear</button>
        </div>
        <div className="can-frame-layout">
          <div className="can-table-scroll frame-list">
            <table className="can-table raw-frame-table">
              <thead><tr><th>Seq</th><th>Time</th><th>CAN ID</th><th>Message</th><th>Source</th><th>DLC</th><th>Payload</th></tr></thead>
              <tbody>
                {rendered.map((frame) => (
                  <tr className={selected?.sequence === frame.sequence ? "selected" : ""} key={frame.sequence} onClick={() => setSelectedSequence(frame.sequence)}>
                    <td className="mono">{frame.sequence}</td>
                    <td className="mono">{formatCanTimestamp(frame.timestamp_microseconds)}</td>
                    <td className="mono can-id">{frame.arbitration_id_hex}</td>
                    <td>{formatCanMessageName(frame.message_name)}</td>
                    <td>{frame.source_ecu ?? "—"}</td>
                    <td className="mono">{frame.dlc}</td>
                    <td className="mono payload-cell">{displayCanPayload(frame.payload_hex)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rendered.length === 0 ? <p className="can-empty">No retained frames match the active filters.</p> : null}
          </div>
          <CanFrameDetail frame={selected} />
        </div>
      </section>
    </div>
  );
}

function CanFrameDetail({ frame }: Readonly<{ frame: CanExplorerFrame | undefined }>) {
  if (frame === undefined) {
    return <aside className="can-detail"><p>Select a retained raw frame to inspect it.</p></aside>;
  }
  return (
    <aside className="can-detail">
      <span className={`decode-badge ${frame.decode_status}`}>{frame.decode_status}</span>
      <h3>{formatCanMessageName(frame.message_name)}</h3>
      <dl>
        <div><dt>Sequence</dt><dd className="mono">{frame.sequence}</dd></div>
        <div><dt>Timestamp</dt><dd className="mono">{frame.timestamp_microseconds} µs</dd></div>
        <div><dt>CAN ID</dt><dd className="mono">{frame.arbitration_id_hex} / {frame.arbitration_id}</dd></div>
        <div><dt>Source ECU</dt><dd>{frame.source_ecu ?? "—"}</dd></div>
        <div><dt>DLC</dt><dd className="mono">{frame.dlc}</dd></div>
        <div><dt>Expected period</dt><dd className="mono">{frame.expected_period_microseconds === null ? "—" : `${frame.expected_period_microseconds} µs`}</dd></div>
      </dl>
      <div className="payload-detail"><span>Exact payload</span><code>{frame.payload_hex || "Empty payload"}</code></div>
      {frame.decode_error === null ? null : <p className="decode-error">{frame.decode_error}</p>}
      <div className="decoded-panel">
        <h4>Decoded engineering signals</h4>
        {frame.decoded_signals.length === 0 ? (
          <p>{frame.decode_status === "unknown" ? "No DBC definition" : "No decoded signals available"}</p>
        ) : (
          <table><thead><tr><th>Signal</th><th>Value</th><th>Unit</th></tr></thead><tbody>
            {frame.decoded_signals.map((signal) => <tr key={signal.signal_name}><td>{signal.signal_name}</td><td className="mono">{String(signal.value)}</td><td>{signal.unit}</td></tr>)}
          </tbody></table>
        )}
      </div>
    </aside>
  );
}
