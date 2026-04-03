import { useRef, useState, useCallback } from "react";
import { CameraView } from "expo-camera";
import { RECORDING_DURATION_MS } from "../constants/config";

type RecordingState = "idle" | "recording" | "done";

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

    // Start recording (expo-camera returns the URI when stopped)
    cameraRef.current.recordAsync({ maxDuration: 65 }).then((result) => {
      if (result?.uri) {
        onComplete(result.uri);
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
