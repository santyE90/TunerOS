"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { fetchCalibrations } from "../../lib/api/client";
import type { CalibrationProfile, CalibrationTable } from "../../lib/api/types";
import {
  calibrationDelta,
  comparisonProfile,
  correspondingTable,
} from "../../lib/calibration/state";

export function CalibrationWorkspace() {
  const [profiles, setProfiles] = useState<CalibrationProfile[]>([]);
  const [selectedId, setSelectedId] = useState("stage-1");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchCalibrations()
      .then((items) => {
        if (active) setProfiles(items);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Calibration catalog unavailable");
        }
      });
    return () => { active = false; };
  }, []);

  const selected = useMemo(
    () => profiles.find((profile) => profile.profile_id === selectedId) ?? profiles[0],
    [profiles, selectedId],
  );
  const baseline = selected === undefined
    ? undefined
    : comparisonProfile(profiles, selected.profile_id);

  if (error !== null) return <p className="calibration-error" role="alert">{error}</p>;
  if (selected === undefined) return <p className="calibration-loading">Loading calibration catalog…</p>;

  return (
    <div className="calibration-workspace">
      <section className="calibration-hero">
        <div>
          <span className="section-kicker">Calibration / Tuning · Simulation only</span>
          <h2>Synthetic powertrain profiles</h2>
          <p>{selected.disclaimer}</p>
        </div>
        <label>
          Inspect profile
          <select value={selected.profile_id} onChange={(event) => setSelectedId(event.target.value)}>
            {profiles.map((profile) => (
              <option value={profile.profile_id} key={profile.profile_id}>
                {profile.display_name}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="calibration-profile-grid">
        <ProfileCard profile={selected} role="Primary" />
        {baseline === undefined ? null : <ProfileCard profile={baseline} role="Comparison" />}
      </section>

      <section className="calibration-parameters">
        <div className="section-heading">
          <div><span className="section-kicker">Immutable run parameters</span><h2>Model response</h2></div>
          <p>Values come from the read-only backend catalog; the C++ simulator remains authoritative.</p>
        </div>
        <table>
          <thead><tr><th>Parameter</th><th>Unit</th><th>{selected.display_name}</th><th>{baseline?.display_name ?? "Comparison"}</th><th>Delta</th></tr></thead>
          <tbody>{selected.parameters.map((parameter) => {
            const other = baseline?.parameters.find((item) => item.name === parameter.name);
            return <tr key={parameter.name}><td>{parameter.name}</td><td>{parameter.unit}</td><td className="mono">{parameter.value}</td><td className="mono">{other?.value ?? "—"}</td><td className="mono">{calibrationDelta(parameter.value, other?.value)}</td></tr>;
          })}</tbody>
        </table>
      </section>

      <section className="calibration-map-list">
        {selected.tables.map((table) => (
          <MapComparison
            key={table.table_id}
            selectedName={selected.display_name}
            baselineName={baseline?.display_name ?? "Comparison"}
            table={table}
            baseline={correspondingTable(baseline, table.table_id)}
          />
        ))}
      </section>

      <section className="calibration-workflow-note">
        <div><span className="section-kicker">Evidence workflow</span><h2>Inspect behavior downstream</h2></div>
        <p>Record Stock and Stage 1 WOT_PULL sessions, then compare their observed CAN-derived signals in Investigation. Calibration metadata is provenance, never a diagnostic input.</p>
        <Link href="/sessions">Open Sessions</Link>
      </section>
    </div>
  );
}

function ProfileCard({ profile, role }: Readonly<{ profile: CalibrationProfile; role: string }>) {
  return <article className="calibration-profile-card"><span>{role}</span><h3>{profile.display_name}</h3><dl><div><dt>Profile ID</dt><dd className="mono">{profile.profile_id}</dd></div><div><dt>Revision</dt><dd>r{profile.revision}</dd></div><div><dt>Synthetic</dt><dd>{profile.synthetic ? "YES" : "NO"}</dd></div></dl><p>{profile.description}</p></article>;
}

function MapComparison({ table, baseline, selectedName, baselineName }: Readonly<{ table: CalibrationTable; baseline?: CalibrationTable; selectedName: string; baselineName: string }>) {
  const oneDimensional = table.column_axis === null;
  return <article className="calibration-map"><header><div><span className="section-kicker">{table.table_id}</span><h3>{table.name}</h3></div><span>{table.value_unit}</span></header>{oneDimensional ? <LineMap table={table} baseline={baseline} /> : null}<div className="calibration-table-scroll"><table><thead>{oneDimensional ? <tr><th>{table.row_axis.name} ({table.row_axis.unit})</th><th>{selectedName}</th><th>{baselineName}</th><th>Delta</th></tr> : <tr><th>{table.row_axis.name} ({table.row_axis.unit}) ↓ / {table.column_axis?.name} ({table.column_axis?.unit}) →</th>{table.column_axis?.breakpoints.map((point) => <th className="mono" key={point}>{point}</th>)}</tr>}</thead><tbody>{oneDimensional ? table.row_axis.breakpoints.map((point, index) => <tr key={point}><th className="mono">{point}</th><td className="mono">{table.values[0]?.[index]}</td><td className="mono">{baseline?.values[0]?.[index] ?? "—"}</td><td className="mono">{calibrationDelta(table.values[0]?.[index] ?? 0, baseline?.values[0]?.[index])}</td></tr>) : table.row_axis.breakpoints.map((point, row) => <tr key={point}><th className="mono">{point}</th>{table.values[row]?.map((value, column) => { const other = baseline?.values[row]?.[column]; return <td key={column}><strong className="mono">{value}</strong><small className="mono">{baselineName} {other ?? "—"} · Δ {calibrationDelta(value, other)}</small></td>; })}</tr>)}</tbody></table></div>{oneDimensional ? null : <footer><span>Cell: {selectedName}</span><span>Small values: {baselineName} and delta</span></footer>}</article>;
}

function LineMap({ table, baseline }: Readonly<{ table: CalibrationTable; baseline?: CalibrationTable }>) {
  const values = [...(table.values[0] ?? []), ...(baseline?.values[0] ?? [])];
  const minimum = Math.min(...values);
  const span = Math.max(0.0001, Math.max(...values) - minimum);
  const points = (source: CalibrationTable | undefined) => (source?.values[0] ?? []).map((value, index, row) => `${(index / Math.max(1, row.length - 1)) * 100},${90 - ((value - minimum) / span) * 75}`).join(" ");
  return <svg className="calibration-line-chart" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label={`${table.name} profile comparison`}><line x1="0" y1="90" x2="100" y2="90" /><polyline className="primary-series" points={points(table)} />{baseline === undefined ? null : <polyline className="baseline-series" points={points(baseline)} />}</svg>;
}
