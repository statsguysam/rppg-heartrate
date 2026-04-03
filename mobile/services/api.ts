import axios from "axios";
import { BACKEND_URL } from "../constants/config";

const client = axios.create({
  baseURL: BACKEND_URL,
  timeout: 120_000, // 2 min — processing takes up to ~30s after upload
  headers: { Accept: "application/json" },
});

export interface AnalyzeResult {
  bpm: number;
  confidence: number;
  waveform: number[];
  waveform_fps: number;
  processing_time_ms: number;
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

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await client.get("/health", { timeout: 5000 });
    return res.status === 200;
  } catch {
    return false;
  }
}
