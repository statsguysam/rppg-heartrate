import AsyncStorage from "@react-native-async-storage/async-storage";
import { BP_CALIBRATION_KEY, BP_CALIBRATION_TTL_DAYS } from "../constants/config";

export interface BPCalibration {
  sbp_offset: number;   // add to model SBP to get calibrated value
  dbp_offset: number;
  cuff_sbp: number;     // cuff reading at calibration time
  cuff_dbp: number;
  calibrated_at: string; // ISO timestamp
}

export async function loadCalibration(): Promise<BPCalibration | null> {
  try {
    const raw = await AsyncStorage.getItem(BP_CALIBRATION_KEY);
    return raw ? (JSON.parse(raw) as BPCalibration) : null;
  } catch {
    return null;
  }
}

export async function saveCalibration(cal: BPCalibration): Promise<void> {
  await AsyncStorage.setItem(BP_CALIBRATION_KEY, JSON.stringify(cal));
}

export async function clearCalibration(): Promise<void> {
  await AsyncStorage.removeItem(BP_CALIBRATION_KEY);
}

export function isCalibrationStale(cal: BPCalibration | null): boolean {
  if (!cal) return true;
  const ageMs = Date.now() - new Date(cal.calibrated_at).getTime();
  return ageMs > BP_CALIBRATION_TTL_DAYS * 24 * 60 * 60 * 1000;
}

/** Derive calibration offsets from a scan paired with a cuff reading. */
export function computeOffsets(
  cuff_sbp: number,
  cuff_dbp: number,
  model_sbp: number,
  model_dbp: number
): BPCalibration {
  return {
    sbp_offset: cuff_sbp - model_sbp,
    dbp_offset: cuff_dbp - model_dbp,
    cuff_sbp,
    cuff_dbp,
    calibrated_at: new Date().toISOString(),
  };
}

/** Apply offsets to a raw model prediction. Null-safe. */
export function applyCalibration(
  model_sbp: number | null | undefined,
  model_dbp: number | null | undefined,
  cal: BPCalibration | null
): { sbp: number | null; dbp: number | null; calibrated: boolean } {
  if (model_sbp == null || model_dbp == null) {
    return { sbp: null, dbp: null, calibrated: false };
  }
  if (!cal) {
    return { sbp: Math.round(model_sbp), dbp: Math.round(model_dbp), calibrated: false };
  }
  return {
    sbp: Math.round(model_sbp + cal.sbp_offset),
    dbp: Math.round(model_dbp + cal.dbp_offset),
    calibrated: true,
  };
}
