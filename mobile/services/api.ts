import axios from "axios";
import { BACKEND_URL } from "../constants/config";

const client = axios.create({
  baseURL: BACKEND_URL,
  timeout: 300_000, // 5 min — processing takes up to ~30s after upload + upload time
  headers: { Accept: "application/json" },
});

export interface AnalyzeResult {
  bpm: number;
  confidence: number;
  waveform: number[];
  waveform_fps: number;
  processing_time_ms: number;
  video_url?: string;
  sbp?: number | null;
  dbp?: number | null;
  bp_confidence?: number | null;  // 0–1
  rmssd_ms?: number | null;
  sdnn_ms?: number | null;
  pnn50?: number | null;
  hrv_confidence?: number | null;
  respiration_bpm?: number | null;
  respiration_confidence?: number | null;
  stress_score?: number | null;          // 0–100
  stress_label?: string | null;          // Low | Normal | Elevated | High
  stress_lf_hf?: number | null;
  stress_confidence?: number | null;
}

export interface Demographics {
  age?: number;
  sex?: string;
  bmi?: number;
}

/**
 * Upload a video file URI and return the heart rate + BP analysis.
 * Demographics are optional but improve BP accuracy.
 */
export async function analyzeVideo(
  fileUri: string,
  demographics: Demographics = {},
  onUploadProgress?: (progress: number) => void
): Promise<AnalyzeResult> {
  const formData = new FormData();
  formData.append("video", {
    uri: fileUri,
    type: "video/mp4",
    name: "face_scan.mp4",
  } as any);
  if (demographics.age != null) formData.append("age", String(demographics.age));
  if (demographics.sex) formData.append("sex", demographics.sex);
  if (demographics.bmi != null) formData.append("bmi", String(demographics.bmi));

  const response = await client.post<AnalyzeResult>("/analyze", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (evt) => {
      if (evt.total && onUploadProgress) {
        onUploadProgress(evt.loaded / evt.total);
      }
    },
  });

  return response.data;
}

export interface ScanRecord {
  bpm: number;
  confidence: number;
  sbp?: number;
  dbp?: number;
  bp_confidence?: number;
  rmssd_ms?: number;
  sdnn_ms?: number;
  pnn50?: number;
  hrv_confidence?: number;
  respiration_bpm?: number;
  respiration_confidence?: number;
  stress_score?: number;
  stress_label?: string;
  stress_lf_hf?: number;
  stress_confidence?: number;
  age?: number;
  sex?: string;
  activity?: string;
  stress?: string;
  caffeine?: string;
  medications?: string;
  video_url?: string;
  comment?: string;
  device_id?: string;
}

export async function saveScan(record: ScanRecord): Promise<void> {
  try {
    await client.post("/scans", record);
  } catch {
    // Non-fatal — don't surface DB errors to user
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await client.get("/health", { timeout: 5000 });
    return res.status === 200;
  } catch {
    return false;
  }
}
