import type {
  DiagnosticEvent,
  DiagnosticSeverity,
  DiagnosticStatus,
  DiagnosticTroubleCode,
} from "../api/types";

const STATUS_ORDER: Record<DiagnosticStatus, number> = {
  active: 0,
  pending: 1,
  historical: 2,
  cleared: 3,
};

export function sortDiagnosticDtcs(dtcs: DiagnosticTroubleCode[]): DiagnosticTroubleCode[] {
  return [...dtcs].sort(
    (left, right) =>
      STATUS_ORDER[left.status] - STATUS_ORDER[right.status] ||
      left.definition.code.localeCompare(right.definition.code),
  );
}

export function filterDiagnosticDtcs(
  dtcs: DiagnosticTroubleCode[],
  status: DiagnosticStatus | "all",
): DiagnosticTroubleCode[] {
  return sortDiagnosticDtcs(
    status === "all" ? dtcs : dtcs.filter((dtc) => dtc.status === status),
  );
}

export function selectedDiagnostic(
  dtcs: DiagnosticTroubleCode[],
  selectedCode: string | null,
): DiagnosticTroubleCode | null {
  return (
    dtcs.find((dtc) => dtc.definition.code === selectedCode) ??
    sortDiagnosticDtcs(dtcs)[0] ??
    null
  );
}

export function canClearDiagnostic(dtc: DiagnosticTroubleCode): boolean {
  return dtc.status === "historical";
}

export function formatDiagnosticStatus(status: DiagnosticStatus | DiagnosticSeverity): string {
  return status[0].toUpperCase() + status.slice(1);
}

export function formatDiagnosticEvent(event: DiagnosticEvent): string {
  const labels: Record<DiagnosticEvent["event_type"], string> = {
    condition_detected: "Pending detected",
    condition_cleared: "Pending condition cleared",
    dtc_confirmed: "Confirmed active",
    dtc_recovered: "Recovered / historical",
    dtc_cleared: "Cleared from diagnostic memory",
  };
  return labels[event.event_type];
}
