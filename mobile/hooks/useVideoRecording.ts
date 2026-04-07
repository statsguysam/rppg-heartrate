import { useRef, useState, useCallback } from "react";
import { CameraView } from "expo-camera";
import { Video } from "react-native-compressor";
import { RECORDING_DURATION_MS } from "../constants/config";

type RecordingState = "idle" | "recording" | "compressing" | "done";

export function useVideoRecording(onComplete: (uri: string) => void) {
  const cameraRef = useRef<CameraView>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [state, setState] = useState<RecordingState>("idle");
  const [elapsed, setElapsed] = useState(0); // seconds elapsed
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const start = useCallback(async () => {
    if (!cameraRef.current || state !== "idle") return;
    setState("recording");
    setElapsed(0);

    // Countdown ticker
    intervalRef.current = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);

    // Auto-stop after 60s
    timerRef.current = setTimeout(async () => {
      await stop();
    }, RECORDING_DURATION_MS);

    // Start recording at 480p to keep file size small (~8MB for 60s)
    cameraRef.current.recordAsync({ maxDuration: 65, videoQuality: "480p" }).then(async (result) => {
      if (result?.uri) {
        setState("compressing");
        try {
          // Compress further on-device before upload (targets ~5MB)
          const compressed = await Video.compress(result.uri, {
            compressionMethod: "manual",
            maxSize: 480,
            bitrate: 800_000, // 800kbps — enough for rPPG colour analysis
          });
          onComplete(compressed);
        } catch {
          // If compression fails, send original — better than nothing
          onComplete(result.uri);
        }
        setState("done");
      }
    });
  }, [state, onComplete]);

  const stop = useCallback(async () => {
    if (!cameraRef.current) return;

    if (timerRef.current) clearTimeout(timerRef.current);
    if (intervalRef.current) clearInterval(intervalRef.current);

    cameraRef.current.stopRecording();
    // setState("done") is handled in the recordAsync promise above
  }, []);

  const reset = useCallback(() => {
    setState("idle");
    setElapsed(0);
  }, []);

  return { cameraRef, state, elapsed, start, stop, reset };
}
