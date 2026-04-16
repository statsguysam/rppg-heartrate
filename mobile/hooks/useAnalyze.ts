import { useState, useCallback } from "react";
import { analyzeVideo, AnalyzeResult, Demographics } from "../services/api";

type Status = "idle" | "uploading" | "processing" | "done" | "error";

export function useAnalyze() {
  const [status, setStatus] = useState<Status>("idle");
  const [uploadProgress, setUploadProgress] = useState(0); // 0–1
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (fileUri: string, demographics: Demographics = {}) => {
    setStatus("uploading");
    setUploadProgress(0);
    setError(null);
    setResult(null);

    try {
      const data = await analyzeVideo(fileUri, demographics, (progress) => {
        setUploadProgress(progress);
        // Once upload is complete, switch to "processing" label
        if (progress >= 1.0) setStatus("processing");
      });
      setResult(data);
      setStatus("done");
    } catch (err: any) {
      const isNetwork = !err?.response && (err?.code === "ECONNABORTED" || err?.message?.includes("Network") || err?.message?.includes("timeout"));
      const message = isNetwork
        ? "Connection failed. Check your internet connection and try again."
        : err?.response?.data?.detail ??
          err?.message ??
          "An unexpected error occurred. Please try again.";
      setError(message);
      setStatus("error");
    }
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setUploadProgress(0);
    setResult(null);
    setError(null);
  }, []);

  return { status, uploadProgress, result, error, analyze, reset };
}
