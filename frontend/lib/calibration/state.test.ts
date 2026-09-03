import { describe, expect, it } from "vitest";

import type { CalibrationProfile } from "../api/types";
import { calibrationDelta, comparisonProfile, correspondingTable } from "./state";

const profiles = [
  { profile_id: "stock", tables: [{ table_id: "boost-target" }] },
  { profile_id: "stage-1", tables: [{ table_id: "boost-target" }] },
] as CalibrationProfile[];

describe("calibration presentation state", () => {
  it("selects the other immutable catalog profile as the comparison", () => {
    expect(comparisonProfile(profiles, "stock")?.profile_id).toBe("stage-1");
    expect(correspondingTable(profiles[0], "boost-target")?.table_id).toBe("boost-target");
  });

  it("formats deterministic signed cell deltas", () => {
    expect(calibrationDelta(125, 90)).toBe("+35.00");
    expect(calibrationDelta(0.82, 0.86)).toBe("-0.04");
    expect(calibrationDelta(1, undefined)).toBe("—");
  });
});
