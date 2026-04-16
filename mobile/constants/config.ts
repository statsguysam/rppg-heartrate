export const RECORDING_DURATION_MS = 60_000;   // 1 minute
export const MIN_DURATION_WARNING_MS = 50_000;  // warn if stopped before 50s
// For production builds EXPO_PUBLIC_BACKEND_URL must be set at build time.
// Fallback is intentionally a non-routable address so failure is obvious.
export const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL ?? "http://BACKEND_NOT_CONFIGURED:8000";

// BP calibration — offsets stored locally, re-prompt after 14 days
export const BP_CALIBRATION_KEY = "bp_calibration_v1";
export const BP_CALIBRATION_TTL_DAYS = 14;
