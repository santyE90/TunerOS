import { describe, expect, it } from "vitest";

import type { InvestigationSignalSeries, SignalSample } from "../api/types";
import { parseInvestigation, parseInvestigationComparison } from "../api/validation";
import {
  buildInvestigationHref,
  canonicalSignal,
  latestAtOrBefore,
  parseInvestigationUrl,
  relativeTimestampMicroseconds,
  toggleInvestigationSignal,
} from "./state";

const key = { message_name: "DmeThermalElectrical", signal_name: "BatteryVoltage" };
const definition = {
  key,
  signal_name: key.signal_name,
  message_name: key.message_name,
  arbitration_id: 0x502,
  arbitration_id_hex: "0x502",
  source_ecu: "TunerOsSimulatedDme",
  unit: "V",
  expected_period_microseconds: 100_000,
};

function sample(timestamp: number, value: number): SignalSample {
  return {
    key,
    value,
    timestamp_microseconds: timestamp,
    frame_sequence: timestamp,
    arbitration_id: 0x502,
    arbitration_id_hex: "0x502",
    message_name: key.message_name,
    source_ecu: "TunerOsSimulatedDme",
    unit: "V",
    freshness: null,
  };
}

describe("investigation state", () => {
  it("parses bounded integer URL state and rejects unsafe selections", () => {
    expect(parseInvestigationUrl(new URLSearchParams("t=4700000"))).toEqual({
      centerMicroseconds: 4_700_000,
      beforeMicroseconds: 2_000_000,
      afterMicroseconds: 2_000_000,
      baselineSessionId: undefined,
      baselineCenterMicroseconds: undefined,
      diagnosticCode: undefined,
      signals: [],
    });
    expect(() => parseInvestigationUrl(new URLSearchParams("t=-1"))).toThrow(
      "non-negative integer",
    );
    expect(() =>
      parseInvestigationUrl(new URLSearchParams("before=30000000&after=1")),
    ).toThrow("30 seconds");
  });

  it("uses latest-at-or-before semantics without interpolation", () => {
    const series: InvestigationSignalSeries = {
      definition,
      samples: [sample(2_000_000, 12.0), sample(3_000_000, 11.8)],
    };
    expect(latestAtOrBefore(series, sample(1_000_000, 14.2), 2_500_000)?.value).toBe(12);
    expect(latestAtOrBefore(series, sample(1_000_000, 14.2), 1_500_000)?.value).toBe(14.2);
    expect(latestAtOrBefore(series, undefined, 1_500_000)).toBeUndefined();
  });

  it("bounds signal selection and constructs stable navigation URLs", () => {
    expect(toggleInvestigationSignal(["a", "b"], "a")).toEqual(["b"]);
    expect(() => toggleInvestigationSignal(["a", "b", "c", "d", "e", "f"], "g")).toThrow(
      "at most 6",
    );
    expect(buildInvestigationHref("abc", 4_700_000, "TUN-DME-003")).toBe(
      "/sessions/abc/investigate?t=4700000&code=TUN-DME-003",
    );
    expect(canonicalSignal(key)).toBe("DmeThermalElectrical.BatteryVoltage");
    expect(relativeTimestampMicroseconds(4_800_000, 4_700_000)).toBe(100_000);
  });

  it("rejects malformed investigation and comparison API payloads", () => {
    expect(() => parseInvestigation({ window: {} })).toThrow("invalid investigation evidence");
    expect(() => parseInvestigationComparison({ primary: {}, baseline: {} })).toThrow(
      "invalid investigation comparison evidence",
    );
  });
});
