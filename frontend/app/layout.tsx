import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "../components/shell/app-shell";
import { TelemetryProvider } from "../components/telemetry/telemetry-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "TunerOS Engineering Workstation",
  description: "Live decoded vehicle telemetry from synthetic TunerOS simulation CAN",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <TelemetryProvider>
          <AppShell>{children}</AppShell>
        </TelemetryProvider>
      </body>
    </html>
  );
}
