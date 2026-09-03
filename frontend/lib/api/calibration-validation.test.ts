import { describe, expect, it } from "vitest";

import { parseCalibration, parseCalibrations } from "./validation";

const profile = {
  profile_id: "stock",
  display_name: "Stock",
  revision: 1,
  description: "Synthetic baseline",
  synthetic: true,
  disclaimer: "Simulation only",
  parameters: [{ name: "Engine output multiplier", value: 1, unit: "ratio" }],
  tables: [
    {
      table_id: "throttle-response",
      name: "Throttle response",
      value_unit: "normalized load",
      row_axis: { name: "Pedal", unit: "normalized", breakpoints: [0, 1] },
      column_axis: null,
      values: [[0, 1]],
    },
  ],
};

describe("calibration API boundary", () => {
  it("accepts explicit typed catalog metadata", () => {
    expect(parseCalibration(profile).profile_id).toBe("stock");
    expect(parseCalibrations([profile])).toHaveLength(1);
  });

  it("rejects malformed axes and non-finite values", () => {
    expect(() => parseCalibration({ ...profile, tables: [{ ...profile.tables[0], row_axis: {} }] }))
      .toThrow(/invalid calibration profile/);
    expect(() => parseCalibration({ ...profile, parameters: [{ name: "x", value: Infinity, unit: "s" }] }))
      .toThrow(/invalid calibration profile/);
  });
});
