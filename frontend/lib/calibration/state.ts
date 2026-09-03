import type { CalibrationProfile, CalibrationTable } from "../api/types";

export function comparisonProfile(
  profiles: CalibrationProfile[],
  selectedId: string,
): CalibrationProfile | undefined {
  return profiles.find((profile) => profile.profile_id !== selectedId);
}

export function correspondingTable(
  profile: CalibrationProfile | undefined,
  tableId: string,
): CalibrationTable | undefined {
  return profile?.tables.find((table) => table.table_id === tableId);
}

export function calibrationDelta(value: number, baseline: number | undefined): string {
  if (baseline === undefined) return "—";
  const delta = value - baseline;
  return `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`;
}
