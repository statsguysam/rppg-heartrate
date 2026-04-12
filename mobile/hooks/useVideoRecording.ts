import { useRef, useState, useCallback, useEffect } from "react";
import { CameraView } from "expo-camera";
import { Accelerometer } from "expo-sensors";
import { activateKeepAwakeAsync, deactivateKeepAwake } from "expo-keep-awake";
import { RECORDING_DURATION_MS } from "../constants/config";

type RecordingState = "idle" | "recording" | "done";

const STABLE_THRESHOLD = 0.08;   // max acceleration magnitude change to be "stable"
const STABLE_REQUIRED_S = 60;    // need 60 stable seconds total

export function useVideoRecording(
  onComplete: (uri: string) => void,
  onError?: (message: string) => void
) {
  const cameraRef = useRef<CameraView>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const accelSub = useRef<any>(null);
  const isStableRef = useRef(true);
  const lastAccel = useRef({ x: 0, y: 0, z: 0 });

  const [state, setState] = useState<RecordingState>("idle");
  const [stableElapsed, setStableElapsed] = useState(0);  // stable seconds counted
  const [isStable, setIsStable] = useState(true);

  // Accelerometer — track if user is moving too much
  const startAccelerometer = useCallback(() => {
    Accelerometer.setUpdateInterval(200);
    accelSub.current = Accelerometer.addListener(({ x, y, z }) => {
      const dx = Math.abs(x - lastAccel.current.x);
      const dy = Math.abs(y - lastAccel.current.y);
      const dz = Math.abs(z - lastAccel.current.z);
      const magnitude = dx + dy + dz;
      lastAccel.current = { x, y, z };

      const stable = magnitude < STABLE_THRESHOLD;
      isStableRef.current = stable;
      setIsStable(stable);
    });
  }, []);

  const stopAccelerometer = useCallback(() => {
    accelSub.current?.remove();
    accelSub.current = null;
  }, []);

  const start = useCallback(async () => {
    if (!cameraRef.current || state !== "idle") return;
    setState("recording");
    setStableElapsed(0);
    setIsStable(true);
    isStableRef.current = true;

    startAccelerometer();
    await activateKeepAwakeAsync();

    // Tick every second — only increment stableElapsed when stable
    intervalRef.current = setInterval(() => {
      if (isStableRef.current) {
        setStableElapsed((prev) => {
          const next = prev + 1;
          if (next >= STABLE_REQUIRED_S) {
            // Stop recording once we have 60 stable seconds
            if (cameraRef.current) cameraRef.current.stopRecording();
          }
          return next;
        });
      }
    }, 1000);

    // Hard cap: stop after 3 minutes regardless
    timerRef.current = setTimeout(async () => {
      if (cameraRef.current) cameraRef.current.stopRecording();
    }, 180_000);

    cameraRef.current.recordAsync({ maxDuration: 185, videoQuality: "480p" }).then((result) => {
      if (result?.uri) {
        onComplete(result.uri);
        setState("done");
      } else {
        setState("idle");
        onError?.("Recording failed: no video file was saved. Please try again.");
      }
    }).catch((err: any) => {
      setState("idle");
      onError?.(err?.message ?? "Recording failed. Please try again.");
    });
  }, [state, onComplete, onError, startAccelerometer]);

  const stop = useCallback(async () => {
    if (!cameraRef.current) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    if (intervalRef.current) clearInterval(intervalRef.current);
    stopAccelerometer();
    deactivateKeepAwake();
    cameraRef.current.stopRecording();
  }, [stopAccelerometer]);

  const reset = useCallback(() => {
    setState("idle");
    setStableElapsed(0);
    setIsStable(true);
    stopAccelerometer();
    deactivateKeepAwake();
  }, [stopAccelerometer]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (intervalRef.current) clearInterval(intervalRef.current);
      stopAccelerometer();
    };
  }, [stopAccelerometer]);

  return { cameraRef, state, elapsed: stableElapsed, isStable, start, stop, reset };
}
