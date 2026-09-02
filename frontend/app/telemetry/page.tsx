import { NoticeStrip } from "../../components/telemetry/notice-strip";
import { SignalTable } from "../../components/telemetry/signal-table";

export default function TelemetryPage() {
  return (
    <div className="telemetry-page">
      <NoticeStrip />
      <div className="page-intro">
        <div>
          <span className="section-kicker">All decoded channels</span>
          <h2>Catalog-driven signal inspection</h2>
        </div>
        <p>
          Canonical engineering values, DBC metadata, source provenance, update timing, and
          freshness. No raw CAN payloads or diagnostic interpretation.
        </p>
      </div>
      <SignalTable />
    </div>
  );
}
