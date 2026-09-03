import { describe, expect, it } from "vitest";

import type {
  SignalDefinition,
  SignalSample,
  TelemetrySnapshot,
  TelemetryUpdateEvent,
} from "../api/types";
import {
  parseSessionDetail,
  parseSessionReplay,
  parseSessions,
  parseSource,
  parseStatus,
  parseWebSocketEvent,
} from "../api/validation";
import {
  calibrationDisplayName,
  formatSessionDuration,
  sessionDisplayName,
} from "../sessions/format";
import {
  formatRawValue,
  metersPerSecondToKilometersPerHour,
  normalizedToPercent,
} from "./format";
import { DASHBOARD_SIGNALS, signalKeyId } from "./signals";
import {
  CHART_HISTORY_CAPACITY,
  INITIAL_TELEMETRY_STATE,
  selectHistory,
  selectSample,
  telemetryReducer,
} from "./state";

const definition: SignalDefinition = {
  key: DASHBOARD_SIGNALS.engineRpm,
  signal_name: "EngineSpeedRpm",
  message_name: "DmeFastEngine",
  arbitration_id: 256,
  arbitration_id_hex: "0x100",
  source_ecu: "TunerOsSimulatedDme",
  unit: "rpm",
  expected_period_microseconds: 10_000,
};

function sample(
  value: number | boolean,
  frameSequence: number,
  timestampMicroseconds = frameSequence * 10_000,
  signalName = "EngineSpeedRpm",
): SignalSample {
  return {
    key: { message_name: "DmeFastEngine", signal_name: signalName },
    value,
    timestamp_microseconds: timestampMicroseconds,
    frame_sequence: frameSequence,
    arbitration_id: 256,
    arbitration_id_hex: "0x100",
    message_name: "DmeFastEngine",
    source_ecu: "TunerOsSimulatedDme",
    unit: signalName === "EngineRunning" ? "boolean" : "rpm",
    freshness: "fresh",
  };
}

function update(
  frameSequence: number,
  signals: SignalSample[],
  timestampMicroseconds = frameSequence * 10_000,
): TelemetryUpdateEvent {
  return {
    type: "telemetry_update",
    timestamp_microseconds: timestampMicroseconds,
    frame_sequence: frameSequence,
    arbitration_id: 256,
    arbitration_id_hex: "0x100",
    message_name: "DmeFastEngine",
    source_ecu: "TunerOsSimulatedDme",
    signals,
  };
}

function snapshot(frameSequence = 4): TelemetrySnapshot {
  const rpm = sample(760, frameSequence);
  return {
    observation_timestamp_microseconds: rpm.timestamp_microseconds,
    last_frame_sequence: frameSequence,
    signals: [rpm],
    statistics: {
      total_frames: frameSequence + 1,
      total_signal_updates: 1,
      latest_timestamp_microseconds: rpm.timestamp_microseconds,
      last_frame_sequence: frameSequence,
      frames_by_message: [
        {
          arbitration_id: 256,
          arbitration_id_hex: "0x100",
          message_name: "DmeFastEngine",
          frames: frameSequence + 1,
        },
      ],
    },
  };
}

describe("telemetry reducer", () => {
  it("treats an initial snapshot as the authoritative complete state", () => {
    const previous = telemetryReducer(INITIAL_TELEMETRY_STATE, {
      type: "updates",
      updates: [update(1, [sample(500, 1)])],
    });
    const state = telemetryReducer(previous, { type: "initial_snapshot", snapshot: snapshot() });

    expect(selectSample(state, DASHBOARD_SIGNALS.engineRpm)?.value).toBe(760);
    expect(state.lastFrameSequence).toBe(4);
    expect(state.statistics.total_frames).toBe(5);
    expect(selectHistory(state, DASHBOARD_SIGNALS.engineRpm)).toEqual([
      { timestampMicroseconds: 40_000, value: 760 },
    ]);

    const afterLateStatus = telemetryReducer(state, {
      type: "status",
      status: {
        service_state: "running",
        gateway_connected: true,
        last_error: null,
        latest_timestamp_microseconds: 0,
        total_frames: 0,
        total_signal_updates: 0,
      },
    });
    expect(afterLateStatus.statistics).toEqual(state.statistics);
  });

  it("applies every signal from one decoded frame in one reducer transition", () => {
    const rpm = sample(800, 1);
    const running = sample(true, 1, 10_000, "EngineRunning");
    const state = telemetryReducer(INITIAL_TELEMETRY_STATE, {
      type: "updates",
      updates: [update(1, [rpm, running])],
    });

    expect(selectSample(state, rpm.key)).toEqual(rpm);
    expect(selectSample(state, running.key)).toEqual(running);
    expect(state.statistics.total_signal_updates).toBe(2);
    expect(state.lastFrameSequence).toBe(1);
  });

  it("applies partial multi-rate DME and DSC frames without clearing other signals", () => {
    const dme = update(1, [sample(810, 1)]);
    const dscSpeed: SignalSample = {
      ...sample(12.5, 2, 20_000, "VehicleSpeed"),
      key: DASHBOARD_SIGNALS.vehicleSpeed,
      arbitration_id: 1312,
      arbitration_id_hex: "0x520",
      message_name: "DscVehicleMotion",
      source_ecu: "TunerOsSimulatedDsc",
      unit: "m/s",
    };
    const dsc = {
      ...update(2, [dscSpeed], 20_000),
      arbitration_id: 1312,
      arbitration_id_hex: "0x520",
      message_name: "DscVehicleMotion",
      source_ecu: "TunerOsSimulatedDsc",
    };
    const state = telemetryReducer(INITIAL_TELEMETRY_STATE, {
      type: "updates",
      updates: [dme, dsc],
    });

    expect(selectSample(state, DASHBOARD_SIGNALS.engineRpm)?.value).toBe(810);
    expect(selectSample(state, DASHBOARD_SIGNALS.vehicleSpeed)?.value).toBe(12.5);
    expect(state.statistics.total_frames).toBe(3);
  });

  it("rejects duplicate or regressing frames without replacing current values", () => {
    const current = telemetryReducer(INITIAL_TELEMETRY_STATE, {
      type: "updates",
      updates: [update(10, [sample(800, 10)])],
    });
    const state = telemetryReducer(current, {
      type: "updates",
      updates: [update(9, [sample(100, 9)])],
    });

    expect(selectSample(state, DASHBOARD_SIGNALS.engineRpm)?.value).toBe(800);
    expect(state.lastFrameSequence).toBe(10);
    expect(state.streamWarning).toContain("Ignored frame sequence 9");
  });

  it("accepts a forward sequence gap and exposes a warning", () => {
    const current = telemetryReducer(INITIAL_TELEMETRY_STATE, {
      type: "initial_snapshot",
      snapshot: snapshot(4),
    });
    const state = telemetryReducer(current, {
      type: "updates",
      updates: [update(7, [sample(770, 7)])],
    });

    expect(state.lastFrameSequence).toBe(7);
    expect(state.streamWarning).toBe("Stream gap: expected frame 5, received 7.");
  });

  it("retains the last telemetry when the backend completes or fails", () => {
    const current = telemetryReducer(INITIAL_TELEMETRY_STATE, {
      type: "initial_snapshot",
      snapshot: snapshot(),
    });
    const completed = telemetryReducer(current, {
      type: "service_state",
      state: "completed",
      error: null,
    });
    const failed = telemetryReducer(completed, {
      type: "service_state",
      state: "failed",
      error: "gateway stopped",
    });

    expect(selectSample(completed, DASHBOARD_SIGNALS.engineRpm)?.value).toBe(760);
    expect(selectSample(failed, DASHBOARD_SIGNALS.engineRpm)?.value).toBe(760);
    expect(failed.serviceError).toBe("gateway stopped");
  });

  it("distinguishes replay source and resets old telemetry on its new snapshot", () => {
    const completed = telemetryReducer(
      telemetryReducer(INITIAL_TELEMETRY_STATE, {
        type: "initial_snapshot",
        snapshot: snapshot(),
      }),
      {
        type: "source",
        source: {
          mode: "replay",
          session_id: "12345678-1234-5678-9234-567812345678",
          session_name: "CITY baseline",
          recording: false,
          recorded_frame_count: 5,
        },
      },
    );
    const reset = telemetryReducer(completed, {
      type: "initial_snapshot",
      snapshot: {
        observation_timestamp_microseconds: null,
        last_frame_sequence: null,
        signals: [],
        statistics: {
          total_frames: 0,
          total_signal_updates: 0,
          latest_timestamp_microseconds: null,
          last_frame_sequence: null,
          frames_by_message: [],
        },
      },
    });

    expect(reset.source.mode).toBe("replay");
    expect(reset.source.session_name).toBe("CITY baseline");
    expect(reset.samples).toEqual({});
    expect(reset.histories).toEqual({});
    expect(reset.lastFrameSequence).toBeNull();
  });

  it("samples presentation history on simulation time and keeps it bounded", () => {
    let state = INITIAL_TELEMETRY_STATE;
    for (let sequence = 1; sequence <= CHART_HISTORY_CAPACITY + 10; sequence += 1) {
      const timestamp = sequence * 50_000;
      state = telemetryReducer(state, {
        type: "updates",
        updates: [update(sequence, [sample(sequence, sequence, timestamp)], timestamp)],
      });
    }

    const history = selectHistory(state, DASHBOARD_SIGNALS.engineRpm);
    expect(history).toHaveLength(CHART_HISTORY_CAPACITY);
    expect(history.at(-1)).toEqual({
      timestampMicroseconds: (CHART_HISTORY_CAPACITY + 10) * 50_000,
      value: CHART_HISTORY_CAPACITY + 10,
    });

    const withinInterval = telemetryReducer(INITIAL_TELEMETRY_STATE, {
      type: "updates",
      updates: [
        update(1, [sample(700, 1, 10_000)], 10_000),
        update(2, [sample(710, 2, 20_000)], 20_000),
      ],
    });
    expect(selectHistory(withinInterval, DASHBOARD_SIGNALS.engineRpm)).toEqual([
      { timestampMicroseconds: 20_000, value: 710 },
    ]);
  });
});

describe("boundary validation and display transforms", () => {
  it("rejects malformed status and stream events", () => {
    expect(() => parseStatus({ service_state: "running" })).toThrow(/invalid telemetry status/);
    expect(() =>
      parseWebSocketEvent({ type: "telemetry_update", frame_sequence: "late" }),
    ).toThrow(/invalid telemetry_update event/);
  });

  it("preserves canonical data while performing display-only conversions", () => {
    expect(metersPerSecondToKilometersPerHour(10)).toBe(36);
    expect(normalizedToPercent(0.42)).toBe(42);
    expect(formatRawValue(undefined)).toBe("—");
    expect(signalKeyId(definition.key)).toBe("DmeFastEngine\u001fEngineSpeedRpm");
  });

  it("runtime-validates session and source API contracts", () => {
    const summary = {
      session_id: "12345678-1234-5678-9234-567812345678",
      name: null,
      created_at_utc: "2026-09-02T12:00:00Z",
      scenario: "city",
      status: "complete",
      frame_count: 1565,
      duration_microseconds: 6_000_000,
      dbc_compatible: true,
      calibration_id: null,
      calibration_revision: null,
    } as const;
    const detail = {
      ...summary,
      format_name: "tuneros.raw_can_session",
      format_version: 1,
      vehicle_profile_id: "bmw-e90-335i-n54-2010-manual",
      can_network: "TunerOS synthetic Classic CAN",
      dbc_name: "tuneros_simulation.dbc",
      dbc_sha256: "a".repeat(64),
      frames_sha256: "b".repeat(64),
      first_timestamp_microseconds: 0,
      last_timestamp_microseconds: 6_000_000,
    };

    expect(parseSessions([summary])).toEqual([summary]);
    expect(parseSessionDetail(detail)).toEqual(detail);
    expect(
      parseSource({
        mode: "replay",
        session_id: summary.session_id,
        session_name: null,
        recording: false,
        recorded_frame_count: 0,
      }).mode,
    ).toBe("replay");
    expect(
      parseSessionReplay({
        session_id: summary.session_id,
        session_name: null,
        source_mode: "replay",
        service_state: "running",
      }).service_state,
    ).toBe("running");
    expect(() => parseSessions([{ ...summary, frame_count: "many" }])).toThrow(/session list/);
    expect(formatSessionDuration(summary.duration_microseconds)).toBe("6.000 s");
    expect(sessionDisplayName(summary)).toBe("Session 12345678");
    expect(calibrationDisplayName(summary)).toBe("Unknown / Legacy");
    expect(
      calibrationDisplayName({ ...summary, calibration_id: "stage-1", calibration_revision: 1 }),
    ).toBe("Stage 1 r1");
  });
});
