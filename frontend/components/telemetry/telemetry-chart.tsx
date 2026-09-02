import type { ChartPoint } from "../../lib/telemetry/state";

export interface ChartSeries {
  label: string;
  color: string;
  points: ChartPoint[];
  transform?: (value: number) => number;
}

interface TelemetryChartProps {
  title: string;
  unit: string;
  series: ChartSeries[];
  description: string;
}

const WIDTH = 720;
const HEIGHT = 210;
const PADDING_X = 42;
const PADDING_TOP = 18;
const PADDING_BOTTOM = 28;

export function TelemetryChart({
  title,
  unit,
  series,
  description,
}: Readonly<TelemetryChartProps>) {
  const plotted = series.map((item) => ({
    ...item,
    points: item.points.map((point) => ({
      timestampMicroseconds: point.timestampMicroseconds,
      value: item.transform?.(point.value) ?? point.value,
    })),
  }));
  const allPoints = plotted.flatMap((item) => item.points);
  const hasData = allPoints.length > 1;
  const xMinimum = hasData ? Math.min(...allPoints.map((point) => point.timestampMicroseconds)) : 0;
  const xMaximum = hasData ? Math.max(...allPoints.map((point) => point.timestampMicroseconds)) : 1;
  const rawMinimum = hasData ? Math.min(...allPoints.map((point) => point.value)) : 0;
  const rawMaximum = hasData ? Math.max(...allPoints.map((point) => point.value)) : 1;
  const valuePadding = Math.max((rawMaximum - rawMinimum) * 0.12, 0.5);
  const yMinimum = rawMinimum - valuePadding;
  const yMaximum = rawMaximum + valuePadding;
  const plotWidth = WIDTH - PADDING_X - 16;
  const plotHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;

  const coordinates = (points: ChartPoint[]) =>
    points
      .map((point) => {
        const x = PADDING_X + ((point.timestampMicroseconds - xMinimum) / (xMaximum - xMinimum || 1)) * plotWidth;
        const y = PADDING_TOP + (1 - (point.value - yMinimum) / (yMaximum - yMinimum || 1)) * plotHeight;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");

  return (
    <article className="chart-panel">
      <header>
        <div>
          <span className="section-kicker">Simulation-time trend</span>
          <h3>{title}</h3>
        </div>
        <div className="chart-legend">
          {plotted.map((item) => (
            <span key={item.label}>
              <i style={{ background: item.color }} aria-hidden="true" />
              {item.label}
            </span>
          ))}
        </div>
      </header>
      {hasData ? (
        <svg
          className="telemetry-chart"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={`${title}: ${description}`}
        >
          {[0, 1, 2, 3].map((line) => {
            const y = PADDING_TOP + (line / 3) * plotHeight;
            return <line className="chart-grid" x1={PADDING_X} x2={WIDTH - 16} y1={y} y2={y} key={line} />;
          })}
          <text className="chart-label" x="4" y={PADDING_TOP + 4}>
            {rawMaximum.toFixed(1)}
          </text>
          <text className="chart-label" x="4" y={PADDING_TOP + plotHeight}>
            {rawMinimum.toFixed(1)}
          </text>
          <text className="chart-label" x={PADDING_X} y={HEIGHT - 7}>
            {(xMinimum / 1_000_000).toFixed(2)} s
          </text>
          <text className="chart-label" textAnchor="end" x={WIDTH - 16} y={HEIGHT - 7}>
            {(xMaximum / 1_000_000).toFixed(2)} s
          </text>
          {plotted.map((item) =>
            item.points.length > 1 ? (
              <polyline
                className="chart-series"
                points={coordinates(item.points)}
                stroke={item.color}
                vectorEffect="non-scaling-stroke"
                key={item.label}
              />
            ) : null,
          )}
        </svg>
      ) : (
        <div className="chart-empty">Waiting for at least two telemetry samples</div>
      )}
      <footer>
        <span>{description}</span>
        <strong>{unit}</strong>
      </footer>
    </article>
  );
}
