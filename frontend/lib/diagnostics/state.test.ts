import { describe, expect, it } from "vitest";

import type {
  DiagnosticEvent,
  DiagnosticFreezeFrame,
  DiagnosticSummary,
  DiagnosticTroubleCode,
} from "../api/types";
import {
  parseDiagnosticDtcs,
  parseDiagnosticEvents,
  parseDiagnosticFreezeFrame,
  parseDiagnosticSummary,
} from "../api/validation";
import { formatDiagnosticTime, formatDiagnosticValue } from "./format";
import {
  canClearDiagnostic,
  filterDiagnosticDtcs,
  formatDiagnosticEvent,
  formatDiagnosticStatus,
  selectedDiagnostic,
} from "./state";

function dtc(code: string, status: DiagnosticTroubleCode["status"]): DiagnosticTroubleCode {
  return {
    definition: {
      code,
      rule_id: "dme.synthetic_test",
      name: "Synthetic test",
      description: "TunerOS test diagnostic",
      severity: "warning",
      source_system: "DME",
      required_signals: [
        { message_name: "DmeThermalElectrical", signal_name: "CoolantTemperature" },
      ],
      confirmation_duration_microseconds: 5_000_000,
      recovery_duration_microseconds: 3_000_000,
      activation_description: "CoolantTemperature > 115 degC",
      recovery_description: "CoolantTemperature <= 110 degC",
    },
    status,
    first_detected_timestamp_microseconds: 1_000_000,
    confirmed_timestamp_microseconds: status === "pending" ? null : 6_000_000,
    last_seen_timestamp_microseconds: 7_000_000,
    resolved_timestamp_microseconds: status === "historical" ? 10_000_000 : null,
    cleared_timestamp_microseconds: status === "cleared" ? 11_000_000 : null,
    occurrence_count: status === "pending" ? 0 : 1,
    freeze_frame_available: status !== "pending",
  };
}

const summary: DiagnosticSummary = {
  observation_timestamp_microseconds: 10_000_000,
  latest_telemetry_frame_sequence: 42,
  retained_event_count: 3,
  total_event_count: 3,
  latest_event_sequence: 2,
  pending_count: 0,
  active_count: 0,
  historical_count: 1,
  cleared_count: 0,
  service_state: "completed",
  source: {
    mode: "replay",
    session_id: "12345678-1234-5678-9234-567812345678",
    session_name: "CITY baseline",
    recording: false,
    recorded_frame_count: 0,
  },
};

const event: DiagnosticEvent = {
  sequence: 2,
  timestamp_microseconds: 10_000_000,
  code: "TUN-DME-001",
  event_type: "dtc_recovered",
  prior_status: "active",
  new_status: "historical",
};

const freezeFrame: DiagnosticFreezeFrame = {
  code: "TUN-DME-001",
  capture_timestamp_microseconds: 6_000_000,
  telemetry_frame_sequence: 24,
  signals: [
    {
      key: { message_name: "DmeThermalElectrical", signal_name: "CoolantTemperature" },
      value: 116,
      unit: "degC",
      source_ecu: "TunerOsSimulatedDme",
      arbitration_id: 0x502,
      arbitration_id_hex: "0x502",
      timestamp_microseconds: 6_000_000,
      telemetry_frame_sequence: 24,
    },
  ],
};

describe("diagnostic API validation", () => {
  it("validates empty state and replay source context", () => {
    const empty = {
      ...summary,
      observation_timestamp_microseconds: null,
      latest_telemetry_frame_sequence: null,
      retained_event_count: 0,
      total_event_count: 0,
      latest_event_sequence: null,
      historical_count: 0,
    };
    expect(parseDiagnosticSummary(empty).source.mode).toBe("replay");
    expect(parseDiagnosticDtcs([])).toEqual([]);
    expect(() => parseDiagnosticSummary({ ...empty, active_count: "zero" })).toThrow(
      /diagnostic summary/,
    );
  });

  it("validates DTCs, events, and immutable freeze-frame transport values", () => {
    expect(parseDiagnosticDtcs([dtc("TUN-DME-001", "active")])[0].status).toBe("active");
    expect(parseDiagnosticEvents([event])[0].event_type).toBe("dtc_recovered");
    expect(parseDiagnosticFreezeFrame(freezeFrame).signals[0].value).toBe(116);
    expect(() =>
      parseDiagnosticFreezeFrame({ ...freezeFrame, telemetry_frame_sequence: "24" }),
    ).toThrow(/freeze frame/);
  });
});

describe("diagnostic presentation state", () => {
  it("sorts by lifecycle priority, filters, and retains explicit selection", () => {
    const dtcs = [
      dtc("TUN-DME-004", "cleared"),
      dtc("TUN-DME-002", "historical"),
      dtc("TUN-DME-003", "pending"),
      dtc("TUN-DME-001", "active"),
    ];
    expect(filterDiagnosticDtcs(dtcs, "all").map((item) => item.status)).toEqual([
      "active",
      "pending",
      "historical",
      "cleared",
    ]);
    expect(filterDiagnosticDtcs(dtcs, "historical")).toEqual([dtcs[1]]);
    expect(selectedDiagnostic(dtcs, "TUN-DME-003")).toEqual(dtcs[2]);
    expect(selectedDiagnostic(dtcs, null)).toEqual(dtcs[3]);
    expect(selectedDiagnostic([], null)).toBeNull();
  });

  it("formats status, transition, simulation time, and freeze-frame values", () => {
    expect(formatDiagnosticStatus("historical")).toBe("Historical");
    expect(formatDiagnosticEvent(event)).toBe("Recovered / historical");
    expect(formatDiagnosticTime(6_000_000)).toBe("6.000000 s");
    expect(formatDiagnosticTime(null)).toBe("—");
    expect(formatDiagnosticValue(true)).toBe("true");
    expect(formatDiagnosticValue(116)).toBe("116");
  });

  it("allows clear only for historical DTCs", () => {
    expect(canClearDiagnostic(dtc("TUN-DME-001", "historical"))).toBe(true);
    expect(canClearDiagnostic(dtc("TUN-DME-001", "active"))).toBe(false);
    expect(canClearDiagnostic(dtc("TUN-DME-001", "pending"))).toBe(false);
    expect(canClearDiagnostic(dtc("TUN-DME-001", "cleared"))).toBe(false);
  });
});
