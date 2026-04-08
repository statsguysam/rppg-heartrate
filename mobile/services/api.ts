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
}

/**
 * Upload a video file URI and return the heart rate analysis result.
 * @param fileUri - local file:// URI from expo-camera
 * @param onUploadProgress - optional callback for upload progress [0–1]
 */
export async function analyzeVideo(
  fileUri: string,
  onUploadProgress?: (progress: number) => void
): Promise<AnalyzeResult> {
  const formData = new FormData();
  formData.append("video", {
    uri: fileUri,
    type: "video/mp4",
    name: "face_scan.mp4",
  } as any);

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
  age?: number;
  sex?: string;
  activity?: string;
  stress?: string;
  caffeine?: string;
  medications?: string;
  video_url?: string;
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
