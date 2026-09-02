import { SessionBrowser } from "../../components/sessions/session-browser";

export default function SessionsPage() {
  return (
    <div className="sessions-page">
      <div className="page-intro">
        <div>
          <span className="section-kicker">Raw-first datalogging</span>
          <h2>Portable CAN sessions</h2>
        </div>
        <p>
          Complete immutable captures. Replay regenerates decoded telemetry through the installed
          authoritative DBC; raw frames remain backend-only.
        </p>
      </div>
      <SessionBrowser />
    </div>
  );
}
