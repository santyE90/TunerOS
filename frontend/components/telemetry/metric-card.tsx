import type { SignalSample } from "../../lib/api/types";
import type { ChartPoint } from "../../lib/telemetry/state";
import { shortSource } from "../../lib/telemetry/signals";

interface MetricCardProps {
  label: string;
  sample?: SignalSample;
  value: string;
  unit: string;
  history?: ChartPoint[];
  prominent?: boolean;
  note?: string;
}

function Sparkline({ points }: Readonly<{ points: ChartPoint[] }>) {
  if (points.length < 2) return <div className="sparkline-empty" aria-hidden="true" />;
  const values = points.map((point) => point.value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = maximum - minimum || 1;
  const path = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * 100;
      const y = 28 - ((point.value - minimum) / range) * 24;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <svg className="sparkline" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={path} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function MetricCard({
  label,
  sample,
  value,
  unit,
  history = [],
  prominent = false,
  note,
}: Readonly<MetricCardProps>) {
  const freshness = sample?.freshness ?? null;
  return (
    <article className={prominent ? "metric-card prominent" : "metric-card"}>
      <div className="metric-heading">
        <h3>{label}</h3>
        <span className={`freshness ${freshness ?? "absent"}`}>
          {freshness === null ? "NO DATA" : freshness.toUpperCase()}
        </span>
      </div>
      <div className="metric-reading">
        <strong>{value}</strong>
        <span>{sample === undefined ? "" : unit}</span>
      </div>
      {prominent ? <Sparkline points={history} /> : null}
      <footer>
        <span>{sample === undefined ? "Awaiting signal" : shortSource(sample.source_ecu)}</span>
        <span className="mono">{sample?.timestamp_microseconds ?? "—"} µs</span>
      </footer>
      {note ? <p className="metric-note">{note}</p> : null}
    </article>
  );
}
