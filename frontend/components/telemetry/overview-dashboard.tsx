"use client";

import type { SignalKey, SignalSample } from "../../lib/api/types";
import {
  formatRawValue,
  metersPerSecondToKilometersPerHour,
  normalizedToPercent,
} from "../../lib/telemetry/format";
import { DASHBOARD_SIGNALS } from "../../lib/telemetry/signals";
import { selectHistory, selectSample } from "../../lib/telemetry/state";
import { MetricCard } from "./metric-card";
import { NoticeStrip } from "./notice-strip";
import { TelemetryChart } from "./telemetry-chart";
import { useTelemetry } from "./telemetry-provider";

function numeric(sample: SignalSample | undefined): number | null {
  return sample !== undefined && typeof sample.value === "number" ? sample.value : null;
}

function fixed(sample: SignalSample | undefined, digits = 1): string {
  const value = numeric(sample);
  return value === null ? "—" : value.toFixed(digits);
}

function percent(sample: SignalSample | undefined): string {
  const value = numeric(sample);
  return value === null ? "—" : normalizedToPercent(value).toFixed(1);
}

function Metric({
  signal,
  label,
  unit,
  display,
  prominent,
  note,
}: Readonly<{
  signal: SignalKey;
  label: string;
  unit: string;
  display?: (sample: SignalSample | undefined) => string;
  prominent?: boolean;
  note?: (sample: SignalSample | undefined) => string | undefined;
}>) {
  const telemetry = useTelemetry();
  const sample = selectSample(telemetry, signal);
  return (
    <MetricCard
      label={label}
      sample={sample}
      value={display?.(sample) ?? formatRawValue(sample)}
      unit={unit}
      history={selectHistory(telemetry, signal)}
      prominent={prominent}
      note={note?.(sample)}
    />
  );
}

export function OverviewDashboard() {
  const telemetry = useTelemetry();
  const history = (key: SignalKey) => selectHistory(telemetry, key);

  return (
    <div className="dashboard-page">
      <NoticeStrip />

      <section className="section-heading">
        <div>
          <span className="section-kicker">Powertrain + motion</span>
          <h2>Primary channels</h2>
        </div>
        <p>Latest decoded engineering values. Stale samples remain visible and are never zeroed.</p>
      </section>

      <section className="primary-metrics" aria-label="Primary vehicle telemetry">
        <Metric signal={DASHBOARD_SIGNALS.engineRpm} label="Engine speed" unit="rpm" prominent />
        <Metric
          signal={DASHBOARD_SIGNALS.vehicleSpeed}
          label="Vehicle speed"
          unit="km/h"
          prominent
          display={(sample) => {
            const value = numeric(sample);
            return value === null ? "—" : metersPerSecondToKilometersPerHour(value).toFixed(1);
          }}
          note={(sample) => {
            const value = numeric(sample);
            return value === null ? undefined : `Display conversion · canonical ${value.toFixed(2)} m/s`;
          }}
        />
        <Metric signal={DASHBOARD_SIGNALS.currentGear} label="Selected gear" unit="gear" />
        <Metric
          signal={DASHBOARD_SIGNALS.throttle}
          label="Throttle position"
          unit="%"
          display={percent}
        />
        <Metric
          signal={DASHBOARD_SIGNALS.engineLoad}
          label="Engine load"
          unit="%"
          display={percent}
        />
      </section>

      <section className="chart-grid-layout" aria-label="Primary live charts">
        <TelemetryChart
          title="Engine speed"
          unit="rpm"
          description="DME engine-speed observations"
          series={[
            {
              label: "RPM",
              color: "var(--chart-rpm)",
              points: history(DASHBOARD_SIGNALS.engineRpm),
            },
          ]}
        />
        <TelemetryChart
          title="Vehicle speed"
          unit="km/h display · canonical m/s"
          description="DSC vehicle-speed observations"
          series={[
            {
              label: "Speed",
              color: "var(--chart-speed)",
              points: history(DASHBOARD_SIGNALS.vehicleSpeed),
              transform: metersPerSecondToKilometersPerHour,
            },
          ]}
        />
      </section>

      <section className="section-heading">
        <div>
          <span className="section-kicker">Thermal + electrical</span>
          <h2>Operating temperatures</h2>
        </div>
        <p>No diagnostic thresholds are applied.</p>
      </section>
      <section className="secondary-metrics thermal-metrics">
        <Metric signal={DASHBOARD_SIGNALS.coolant} label="Coolant" unit="°C" display={fixed} />
        <Metric signal={DASHBOARD_SIGNALS.oil} label="Oil" unit="°C" display={fixed} />
        <Metric signal={DASHBOARD_SIGNALS.intakeAir} label="Intake air" unit="°C" display={fixed} />
        <Metric signal={DASHBOARD_SIGNALS.battery} label="Battery" unit="V" display={fixed} />
      </section>
      <TelemetryChart
        title="Thermal channels"
        unit="°C"
        description="Independent 10 Hz DME thermal signals"
        series={[
          { label: "Coolant", color: "var(--chart-coolant)", points: history(DASHBOARD_SIGNALS.coolant) },
          { label: "Oil", color: "var(--chart-oil)", points: history(DASHBOARD_SIGNALS.oil) },
          { label: "Intake air", color: "var(--chart-iat)", points: history(DASHBOARD_SIGNALS.intakeAir) },
        ]}
      />

      <section className="section-heading">
        <div>
          <span className="section-kicker">Air + requested load</span>
          <h2>Driver and scenario demand</h2>
        </div>
        <p>MAP remains absolute pressure; normalized channels are percentage-formatted here only.</p>
      </section>
      <section className="secondary-metrics air-metrics">
        <Metric
          signal={DASHBOARD_SIGNALS.manifoldPressure}
          label="Manifold pressure absolute"
          unit="kPa abs"
          display={fixed}
        />
        <Metric
          signal={DASHBOARD_SIGNALS.accelerator}
          label="Accelerator pedal"
          unit="%"
          display={percent}
        />
        <Metric
          signal={DASHBOARD_SIGNALS.requestedLoad}
          label="Requested scenario load"
          unit="%"
          display={percent}
        />
      </section>
      <TelemetryChart
        title="Demand channels"
        unit="% display · canonical normalized"
        description="Throttle, accelerator, and scenario-load observations"
        series={[
          { label: "Throttle", color: "var(--chart-throttle)", points: history(DASHBOARD_SIGNALS.throttle), transform: normalizedToPercent },
          { label: "Accelerator", color: "var(--chart-accelerator)", points: history(DASHBOARD_SIGNALS.accelerator), transform: normalizedToPercent },
          { label: "Load", color: "var(--chart-load)", points: history(DASHBOARD_SIGNALS.engineLoad), transform: normalizedToPercent },
        ]}
      />

      <section className="section-heading">
        <div>
          <span className="section-kicker">DSC observation</span>
          <h2>Wheel speeds</h2>
        </div>
        <p>Four independently decoded channels; current simulation derives equal values.</p>
      </section>
      <section className="wheel-grid" aria-label="Wheel speeds">
        <Metric signal={DASHBOARD_SIGNALS.frontLeftWheel} label="Front left" unit="m/s" display={(sample) => fixed(sample, 2)} />
        <Metric signal={DASHBOARD_SIGNALS.frontRightWheel} label="Front right" unit="m/s" display={(sample) => fixed(sample, 2)} />
        <Metric signal={DASHBOARD_SIGNALS.rearLeftWheel} label="Rear left" unit="m/s" display={(sample) => fixed(sample, 2)} />
        <Metric signal={DASHBOARD_SIGNALS.rearRightWheel} label="Rear right" unit="m/s" display={(sample) => fixed(sample, 2)} />
      </section>
    </div>
  );
}
