import type { SignalKey } from "../api/types";

export const DASHBOARD_SIGNALS = {
  engineRpm: { message_name: "DmeFastEngine", signal_name: "EngineSpeedRpm" },
  throttle: { message_name: "DmeFastEngine", signal_name: "ThrottlePosition" },
  engineLoad: { message_name: "DmeFastEngine", signal_name: "EngineLoad" },
  engineRunning: { message_name: "DmeFastEngine", signal_name: "EngineRunning" },
  manifoldPressure: {
    message_name: "DmeAirLoad",
    signal_name: "ManifoldPressureAbsolute",
  },
  accelerator: { message_name: "DmeAirLoad", signal_name: "AcceleratorPedalPosition" },
  requestedLoad: { message_name: "DmeAirLoad", signal_name: "RequestedScenarioLoad" },
  coolant: { message_name: "DmeThermalElectrical", signal_name: "CoolantTemperature" },
  oil: { message_name: "DmeThermalElectrical", signal_name: "OilTemperature" },
  intakeAir: {
    message_name: "DmeThermalElectrical",
    signal_name: "IntakeAirTemperature",
  },
  battery: { message_name: "DmeThermalElectrical", signal_name: "BatteryVoltage" },
  vehicleSpeed: { message_name: "DscVehicleMotion", signal_name: "VehicleSpeed" },
  currentGear: { message_name: "DscVehicleMotion", signal_name: "CurrentGear" },
  frontLeftWheel: { message_name: "DscWheelSpeeds", signal_name: "FrontLeftWheelSpeed" },
  frontRightWheel: { message_name: "DscWheelSpeeds", signal_name: "FrontRightWheelSpeed" },
  rearLeftWheel: { message_name: "DscWheelSpeeds", signal_name: "RearLeftWheelSpeed" },
  rearRightWheel: { message_name: "DscWheelSpeeds", signal_name: "RearRightWheelSpeed" },
} satisfies Record<string, SignalKey>;

export function signalKeyId(key: SignalKey): string {
  return `${key.message_name}\u001f${key.signal_name}`;
}

export function shortSource(source: string): string {
  if (source === "TunerOsSimulatedDme") return "DME";
  if (source === "TunerOsSimulatedDsc") return "DSC";
  return source;
}
