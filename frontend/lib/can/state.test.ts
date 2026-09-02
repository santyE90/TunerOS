import { describe, expect, it } from "vitest";

import type {
  CanExplorerFrame,
  CanExplorerStatistics,
  CanFrameEvent,
  CanMessageStatistics,
  InitialCanSnapshotEvent,
  TelemetrySource,
} from "../api/types";
import { parseCanFrame, parseCanWebSocketEvent } from "../api/validation";
import { displayCanPayload, formatCanMessageName, formatCanTimestamp } from "./format";
import {
  CAN_CLIENT_BUFFER_CAPACITY,
  canExplorerReducer,
  filterCanFrames,
  INITIAL_CAN_EXPLORER_STATE,
} from "./state";

const liveSource: TelemetrySource = {
  mode: "live",
  session_id: null,
  session_name: null,
  recording: false,
  recorded_frame_count: 0,
};

function frame(sequence: number, arbitrationId = 0x500): CanExplorerFrame {
  return {
    sequence,
    timestamp_microseconds: sequence * 10_000,
    arbitration_id: arbitrationId,
    arbitration_id_hex: `0x${arbitrationId.toString(16).toUpperCase().padStart(3, "0")}`,
    dlc: 5,
    payload: [112, 23, 128, 64, 1],
    payload_hex: "70 17 80 40 01",
    message_name: arbitrationId === 0x500 ? "DmeFastEngine" : null,
    source_ecu: arbitrationId === 0x500 ? "TunerOsSimulatedDme" : null,
    expected_period_microseconds: arbitrationId === 0x500 ? 10_000 : null,
    decode_status: arbitrationId === 0x500 ? "decoded" : "unknown",
    decode_error: null,
    decoded_signals:
      arbitrationId === 0x500
        ? [{ signal_name: "EngineSpeedRpm", value: 1500, unit: "rpm" }]
        : [],
  };
}

function message(sequence: number, arbitrationId = 0x500): CanMessageStatistics {
  const item = frame(sequence, arbitrationId);
  return {
    arbitration_id: arbitrationId,
    arbitration_id_hex: item.arbitration_id_hex,
    message_name: item.message_name,
    source_ecu: item.source_ecu,
    retained_frame_count: sequence + 1,
    total_frame_count: sequence + 1,
    first_timestamp_microseconds: 0,
    latest_timestamp_microseconds: item.timestamp_microseconds,
    expected_period_microseconds: item.expected_period_microseconds,
    observed_average_period_microseconds: sequence === 0 ? null : 10_000,
    observed_frequency_hz: sequence === 0 ? null : 100,
    latest_dlc: item.dlc,
  };
}

function statistics(sequence: number | null, source = liveSource): CanExplorerStatistics {
  return {
    retained_frame_count: sequence === null ? 0 : Math.min(sequence + 1, 4096),
    total_frame_count: sequence === null ? 0 : sequence + 1,
    unique_id_count: sequence === null ? 0 : 1,
    oldest_retained_timestamp_microseconds: sequence === null ? null : 0,
    newest_retained_timestamp_microseconds: sequence === null ? null : sequence * 10_000,
    last_sequence: sequence,
    source,
  };
}

function event(sequence: number, arbitrationId = 0x500): CanFrameEvent {
  return {
    type: "can_frame",
    frame: frame(sequence, arbitrationId),
    statistics: statistics(sequence),
    message_statistics: message(sequence, arbitrationId),
  };
}

function initial(frames: CanExplorerFrame[] = []): InitialCanSnapshotEvent {
  const latest = frames.at(-1)?.sequence ?? null;
  return {
    type: "initial_can_snapshot",
    frames,
    statistics: statistics(latest),
    messages: frames.length === 0 ? [] : [message(latest ?? 0)],
    service_state: "running",
  };
}

describe("CAN explorer reducer", () => {
  it("uses the raw snapshot as authoritative initialization", () => {
    const state = canExplorerReducer(INITIAL_CAN_EXPLORER_STATE, {
      type: "initial",
      event: initial([frame(7)]),
    });
    expect(state.displayedFrames.map((item) => item.sequence)).toEqual([7]);
    expect(state.statistics.last_sequence).toBe(7);
    expect(state.initialized).toBe(true);
  });

  it("retains a bounded tail and preserves duplicate raw observations", () => {
    let state = canExplorerReducer(INITIAL_CAN_EXPLORER_STATE, {
      type: "initial",
      event: initial(),
    });
    for (let sequence = 0; sequence <= CAN_CLIENT_BUFFER_CAPACITY; sequence += 1) {
      state = canExplorerReducer(state, { type: "frames", events: [event(sequence)] });
    }
    expect(state.currentFrames).toHaveLength(CAN_CLIENT_BUFFER_CAPACITY);
    expect(state.currentFrames[0].sequence).toBe(1);
    expect(state.currentFrames.at(-1)?.sequence).toBe(CAN_CLIENT_BUFFER_CAPACITY);
    expect(state.currentFrames[1].payload_hex).toBe(state.currentFrames[2].payload_hex);
  });

  it("rejects duplicate/regressing sequences and reports forward gaps", () => {
    const started = canExplorerReducer(INITIAL_CAN_EXPLORER_STATE, {
      type: "frames",
      events: [event(2)],
    });
    const duplicate = canExplorerReducer(started, { type: "frames", events: [event(2)] });
    const gap = canExplorerReducer(duplicate, { type: "frames", events: [event(5)] });
    expect(duplicate.currentFrames).toHaveLength(1);
    expect(duplicate.streamWarning).toContain("Ignored raw sequence");
    expect(gap.streamWarning).toContain("expected 3, received 5");
  });

  it("freezes only displayed rows and reconciles on resume", () => {
    let state = canExplorerReducer(INITIAL_CAN_EXPLORER_STATE, {
      type: "frames",
      events: [event(0)],
    });
    state = canExplorerReducer(state, { type: "toggle_freeze" });
    state = canExplorerReducer(state, { type: "frames", events: [event(1), event(2)] });
    expect(state.displayedFrames.map((item) => item.sequence)).toEqual([0]);
    expect(state.currentFrames.map((item) => item.sequence)).toEqual([0, 1, 2]);
    expect(state.framesPassedWhileFrozen).toBe(2);
    state = canExplorerReducer(state, { type: "toggle_freeze" });
    expect(state.displayedFrames.map((item) => item.sequence)).toEqual([0, 1, 2]);
    expect(state.framesPassedWhileFrozen).toBe(0);
  });
});

describe("CAN explorer validation, filters, and formatting", () => {
  it("validates explicit byte arrays and raw WebSocket events", () => {
    expect(parseCanFrame(frame(0)).payload).toEqual([112, 23, 128, 64, 1]);
    expect(displayCanPayload(parseCanFrame(frame(0)).payload_hex)).toBe("70 17 80 40 01");
    expect(displayCanPayload("")).toBe("—");
    expect(formatCanMessageName(frame(1, 0x123).message_name)).toBe("Unknown");
    expect(parseCanWebSocketEvent(initial([frame(0)])).type).toBe("initial_can_snapshot");
    expect(() => parseCanFrame({ ...frame(0), dlc: 4 })).toThrow(/raw CAN frame/);
    expect(() => parseCanFrame({ ...frame(0), payload: [300, 0, 0, 0, 0] })).toThrow(
      /raw CAN frame/,
    );
  });

  it("filters known and unknown frames without decoding in React", () => {
    const frames = [frame(0), frame(1, 0x123)];
    expect(filterCanFrames(frames, { canId: "123", messageName: "", sourceEcu: "", text: "" })).toEqual([frames[1]]);
    expect(filterCanFrames(frames, { canId: "", messageName: "unknown", sourceEcu: "", text: "" })).toEqual([frames[1]]);
    expect(filterCanFrames(frames, { canId: "", messageName: "", sourceEcu: "dme", text: "" })).toEqual([frames[0]]);
    expect(filterCanFrames(frames, { canId: "", messageName: "", sourceEcu: "", text: "70 17" })).toEqual(frames);
    expect(formatCanTimestamp(6_000_000)).toBe("6.000000 s");
  });

  it("retains replay source context from the authoritative snapshot", () => {
    const replaySource: TelemetrySource = {
      ...liveSource,
      mode: "replay",
      session_id: "12345678-1234-5678-9234-567812345678",
      session_name: "CITY baseline",
    };
    const snapshot = initial();
    snapshot.statistics = statistics(null, replaySource);
    const state = canExplorerReducer(INITIAL_CAN_EXPLORER_STATE, {
      type: "initial",
      event: snapshot,
    });
    expect(state.source).toEqual(replaySource);
  });
});
