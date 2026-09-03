"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { StatusBar } from "../telemetry/status-bar";

const navigation = [
  { label: "Overview", href: "/", enabled: true, marker: "OV" },
  { label: "Telemetry", href: "/telemetry", enabled: true, marker: "TM" },
  { label: "Sessions", href: "/sessions", enabled: true, marker: "SS" },
  { label: "CAN Explorer", href: "/can", enabled: true, marker: "CN" },
  { label: "Diagnostics", href: "/diagnostics", enabled: true, marker: "DX" },
  { label: "Calibration", enabled: false, marker: "CL" },
  { label: "System", enabled: false, marker: "SY" },
] as const;

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  const pageTitle =
    pathname.includes("/investigate")
      ? "Diagnostic investigation"
      : pathname === "/telemetry"
      ? "Signal telemetry"
      : pathname === "/can"
        ? "Raw CAN explorer"
        : pathname === "/diagnostics"
          ? "Diagnostics"
      : pathname === "/sessions"
        ? "Recorded sessions"
        : "Engineering overview";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            T
          </div>
          <div>
            <strong>TunerOS</strong>
            <span>Engineering workstation</span>
          </div>
        </div>

        <nav className="primary-nav" aria-label="Primary navigation">
          {navigation.map((item) =>
            item.enabled ? (
              <Link
                className={pathname === item.href ? "nav-item active" : "nav-item"}
                href={item.href}
                key={item.label}
              >
                <span className="nav-marker" aria-hidden="true">
                  {item.marker}
                </span>
                <span>{item.label}</span>
              </Link>
            ) : (
              <span className="nav-item disabled" key={item.label} aria-disabled="true">
                <span className="nav-marker" aria-hidden="true">
                  {item.marker}
                </span>
                <span>{item.label}</span>
                <small>Later</small>
              </span>
            ),
          )}
        </nav>

        <section className="vehicle-identity" aria-labelledby="vehicle-title">
          <span className="section-kicker">Reference vehicle</span>
          <h2 id="vehicle-title">2010 BMW 335i</h2>
          <dl>
            <div>
              <dt>Platform</dt>
              <dd>E90</dd>
            </div>
            <div>
              <dt>Engine</dt>
              <dd>N54B30</dd>
            </div>
            <div>
              <dt>Gearbox</dt>
              <dd>6-speed manual</dd>
            </div>
          </dl>
          <p>Static reference metadata · synthetic simulation CAN</p>
        </section>
      </aside>

      <div className="workspace">
        <header className="workspace-header">
          <div>
            <span className="section-kicker">
              {pathname.includes("/investigate") ? "Recorded session evidence" : "Live vehicle data"}
            </span>
            <h1>{pageTitle}</h1>
          </div>
          <div className="header-context">
            <span>LOCAL / SIM</span>
            <strong>CAN → DBC → TELEMETRY</strong>
          </div>
        </header>
        <StatusBar />
        <main className="workspace-main">{children}</main>
      </div>
    </div>
  );
}
