"use client";

import { useMemo, useState } from "react";

import type { SignalDefinition, SignalSample } from "../../lib/api/types";
import { formatRawValue, formatSimulationTime } from "../../lib/telemetry/format";
import { shortSource, signalKeyId } from "../../lib/telemetry/signals";
import { selectHistory } from "../../lib/telemetry/state";
import { TelemetryChart } from "./telemetry-chart";
import { useTelemetry } from "./telemetry-provider";

type SortMode = "signal" | "message";

function SignalRow({
  definition,
  sample,
  selected,
  onSelect,
}: Readonly<{
  definition: SignalDefinition;
  sample?: SignalSample;
  selected: boolean;
  onSelect: () => void;
}>) {
  return (
    <tr className={selected ? "selected" : undefined}>
      <td>
        <button type="button" className="signal-select" onClick={onSelect}>
          <strong>{definition.signal_name}</strong>
          <span className="canonical-key">{definition.message_name}.{definition.signal_name}</span>
        </button>
      </td>
      <td className="value-cell">{formatRawValue(sample)}</td>
      <td>{definition.unit}</td>
      <td title={definition.source_ecu}>{shortSource(definition.source_ecu)}</td>
      <td>{definition.message_name}</td>
      <td className="mono">{definition.arbitration_id_hex}</td>
      <td className="mono">{formatSimulationTime(sample?.timestamp_microseconds ?? null)}</td>
      <td>
        <span className={`freshness ${sample?.freshness ?? "absent"}`}>
          {sample?.freshness?.toUpperCase() ?? "NO DATA"}
        </span>
      </td>
      <td className="mono">{(definition.expected_period_microseconds / 1_000).toFixed(0)} ms</td>
    </tr>
  );
}

export function SignalTable() {
  const telemetry = useTelemetry();
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [sort, setSort] = useState<SortMode>("message");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const definitions = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return telemetry.catalog
      .filter(
        (definition) =>
          (source === "all" || definition.source_ecu === source) &&
          (normalizedQuery === "" ||
            definition.signal_name.toLowerCase().includes(normalizedQuery) ||
            definition.message_name.toLowerCase().includes(normalizedQuery)),
      )
      .toSorted((left, right) => {
        const primary =
          sort === "signal"
            ? left.signal_name.localeCompare(right.signal_name)
            : left.message_name.localeCompare(right.message_name);
        return primary || left.signal_name.localeCompare(right.signal_name);
      });
  }, [query, sort, source, telemetry.catalog]);

  const sources = useMemo(
    () => [...new Set(telemetry.catalog.map((definition) => definition.source_ecu))].toSorted(),
    [telemetry.catalog],
  );
  const selected = telemetry.catalog.find((definition) => signalKeyId(definition.key) === selectedId);
  const selectedSample = selected === undefined ? undefined : telemetry.samples[signalKeyId(selected.key)];

  return (
    <div className="telemetry-inspector">
      <section className="table-panel">
        <header className="table-toolbar">
          <div>
            <span className="section-kicker">Authoritative catalog</span>
            <h2>Decoded signals</h2>
          </div>
          <label>
            <span>Filter</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Signal or message"
            />
          </label>
          <label>
            <span>Source ECU</span>
            <select value={source} onChange={(event) => setSource(event.target.value)}>
              <option value="all">All sources</option>
              {sources.map((item) => (
                <option value={item} key={item}>
                  {shortSource(item)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Sort</span>
            <select value={sort} onChange={(event) => setSort(event.target.value as SortMode)}>
              <option value="message">Message</option>
              <option value="signal">Signal</option>
            </select>
          </label>
        </header>

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Signal</th>
                <th>Value</th>
                <th>Unit</th>
                <th>Source</th>
                <th>Message</th>
                <th>CAN ID</th>
                <th>Timestamp</th>
                <th>Freshness</th>
                <th>Period</th>
              </tr>
            </thead>
            <tbody>
              {definitions.map((definition) => {
                const id = signalKeyId(definition.key);
                return (
                  <SignalRow
                    definition={definition}
                    sample={telemetry.samples[id]}
                    selected={selectedId === id}
                    onSelect={() => setSelectedId(id)}
                    key={id}
                  />
                );
              })}
            </tbody>
          </table>
          {definitions.length === 0 ? (
            <div className="table-empty">
              {telemetry.catalog.length === 0
                ? "Catalog unavailable. Start the local FastAPI service."
                : "No signals match the current filters."}
            </div>
          ) : null}
        </div>
      </section>

      <aside className="signal-detail" aria-live="polite">
        {selected === undefined ? (
          <div className="detail-empty">
            <span className="section-kicker">Signal detail</span>
            <h2>Select a signal</h2>
            <p>Inspect its canonical key, provenance, timing, and recent local trend.</p>
          </div>
        ) : (
          <>
            <span className="section-kicker">Signal detail</span>
            <h2>{selected.signal_name}</h2>
            <div className="detail-value">
              <strong>{formatRawValue(selectedSample)}</strong>
              <span>{selectedSample === undefined ? "" : selected.unit}</span>
            </div>
            <dl className="detail-list">
              <div><dt>Canonical key</dt><dd className="mono">{selected.message_name}.{selected.signal_name}</dd></div>
              <div><dt>Source ECU</dt><dd>{selected.source_ecu}</dd></div>
              <div><dt>Message</dt><dd>{selected.message_name}</dd></div>
              <div><dt>CAN ID</dt><dd className="mono">{selected.arbitration_id_hex}</dd></div>
              <div><dt>Timestamp</dt><dd className="mono">{selectedSample?.timestamp_microseconds ?? "—"} µs</dd></div>
              <div><dt>Expected period</dt><dd>{(selected.expected_period_microseconds / 1_000).toFixed(0)} ms</dd></div>
              <div><dt>Freshness</dt><dd>{selectedSample?.freshness ?? "No data"}</dd></div>
            </dl>
            <TelemetryChart
              title={selected.signal_name}
              unit={selected.unit}
              description="Bounded presentation-only local history"
              series={[
                {
                  label: selected.signal_name,
                  color: "var(--accent)",
                  points: selectHistory(telemetry, selected.key),
                },
              ]}
            />
          </>
        )}
      </aside>
    </div>
  );
}
