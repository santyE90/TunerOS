export function formatCanTimestamp(timestampMicroseconds: number): string {
  return `${(timestampMicroseconds / 1_000_000).toFixed(6)} s`;
}

export function formatCanFrequency(frequency: number | null): string {
  return frequency === null ? "—" : `${frequency.toFixed(2)} Hz`;
}

export function formatExpectedFrequency(periodMicroseconds: number | null): string {
  return periodMicroseconds === null ? "—" : `${(1_000_000 / periodMicroseconds).toFixed(2)} Hz`;
}

export function formatCanMessageName(messageName: string | null): string {
  return messageName ?? "Unknown";
}

export function displayCanPayload(payloadHex: string): string {
  return payloadHex || "—";
}
