import React, { useEffect } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  Alert,
} from "react-native";
import { CameraView, useCameraPermissions, useMicrophonePermissions } from "expo-camera";
import { router, useLocalSearchParams } from "expo-router";

import { useVideoRecording } from "../hooks/useVideoRecording";
import { useAnalyze } from "../hooks/useAnalyze";
import UploadProgress from "../components/UploadProgress";
import ErrorBanner from "../components/ErrorBanner";
import { MIN_DURATION_WARNING_MS } from "../constants/config";

export default function ScanScreen() {
  const { age, sex, activity, stress, caffeine, medications, calibration, cuff_sbp, cuff_dbp, return_to } =
    useLocalSearchParams<{
      age: string; sex: string; activity: string;
      stress: string; caffeine: string; medications: string;
      calibration?: string; cuff_sbp?: string; cuff_dbp?: string; return_to?: string;
    }>();
  const [permission, requestPermission] = useCameraPermissions();
  const [micPermission, requestMicPermission] = useMicrophonePermissions();
  const { status: analyzeStatus, uploadProgress, result, error, analyze, reset: resetAnalyze } = useAnalyze();

  const handleRecordingComplete = async (uri: string) => {
    const demographics = {
      age: age ? parseInt(age, 10) : undefined,
      sex: sex || undefined,
      // BMI not collected yet — omitted. Safe: server treats missing as population mean.
    };
    await analyze(uri, demographics);
  };

  const handleRecordingError = (message: string) => {
    Alert.alert("Recording Failed", message, [{ text: "OK" }]);
  };

  const { cameraRef, state: recordState, elapsed, isStable, start, stop, reset: resetRecording } =
    useVideoRecording(handleRecordingComplete, handleRecordingError);

  useEffect(() => {
    if (analyzeStatus === "done" && result) {
      router.replace({
        pathname: "/result",
        params: {
          bpm: result.bpm.toString(),
          confidence: result.confidence.toString(),
          waveform: JSON.stringify(result.waveform),
          waveform_fps: result.waveform_fps.toString(),
          age: age ?? "",
          sex: sex ?? "",
          activity: activity ?? "",
          stress: stress ?? "",
          caffeine: caffeine ?? "",
          medications: medications ?? "",
          video_url: result.video_url ?? "",
          sbp: result.sbp != null ? String(result.sbp) : "",
          dbp: result.dbp != null ? String(result.dbp) : "",
          bp_confidence: result.bp_confidence != null ? String(result.bp_confidence) : "",
          calibration: calibration ?? "",
          cuff_sbp: cuff_sbp ?? "",
          cuff_dbp: cuff_dbp ?? "",
          return_to: return_to ?? "",
        },
      });
      resetRecording();
      resetAnalyze();
    } else if (analyzeStatus === "error" && error) {
      Alert.alert(
        "Analysis Failed",
        error,
        [{ text: "Try Again", onPress: () => { resetRecording(); resetAnalyze(); } }]
      );
    }
  }, [analyzeStatus, result, error]);

  const handleReset = () => {
    resetRecording();
    resetAnalyze();
  };

  const handleStopEarly = () => {
    const elapsed_ms = elapsed * 1000;
    if (elapsed_ms < MIN_DURATION_WARNING_MS) {
      Alert.alert(
        "Too Short",
        `Please record at least 50 stable seconds for an accurate reading. Current: ${elapsed}s stable`,
        [
          { text: "Keep Recording", style: "cancel" },
          { text: "Stop Anyway", style: "destructive", onPress: stop },
        ]
      );
    } else {
      stop();
    }
  };

  if (!permission || !micPermission) return <View style={styles.container} />;

  if (!permission.granted || !micPermission.granted) {
    const requestAll = async () => {
      if (!permission.granted) await requestPermission();
      if (!micPermission.granted) await requestMicPermission();
    };
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.permissionContainer}>
          <Text style={styles.permissionTitle}>Permissions Required</Text>
          <Text style={styles.permissionSubtitle}>
            Heart Rate Monitor needs camera and microphone access to record video for heart rate analysis.
          </Text>
          <TouchableOpacity style={styles.primaryButton} onPress={requestAll}>
            <Text style={styles.primaryButtonText}>Grant Permissions</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const isProcessing = analyzeStatus === "uploading" || analyzeStatus === "processing";
  const countdown = Math.max(0, 60 - elapsed);
  const progress = elapsed / 60;

  return (
    <View style={styles.container}>
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFillObject}
        facing="front"
        mode="video"
      />

      <View style={styles.ovalGuide} />

      {recordState === "idle" && (
        <SafeAreaView style={styles.topOverlay}>
          <View style={styles.instructionCard}>
            <Text style={styles.instructionTitle}>Measure Heart Rate</Text>
            <Text style={styles.instructionText}>
              Position your face in the oval · Stay still · Ensure good lighting
            </Text>
          </View>
        </SafeAreaView>
      )}

      {recordState === "recording" && (
        <SafeAreaView style={styles.topOverlay}>
          <View style={[styles.timerContainer, !isStable && styles.timerContainerMoving]}>
            <View style={[styles.recordingDot, !isStable && styles.recordingDotMoving]} />
            <Text style={styles.timerText}>
              {isStable ? `${countdown}s remaining` : "Hold still! Timer paused"}
            </Text>
          </View>
          {!isStable && (
            <View style={styles.motionWarning}>
              <Text style={styles.motionWarningText}>⚠ Movement detected — stay still for accurate results</Text>
            </View>
          )}
          <View style={styles.progressBarBackground}>
            <View style={[styles.progressBarFill, { width: `${progress * 100}%` }]} />
          </View>
        </SafeAreaView>
      )}

      {analyzeStatus === "error" && error && (
        <SafeAreaView style={styles.bottomOverlay}>
          <ErrorBanner message={error} onRetry={handleReset} />
        </SafeAreaView>
      )}

      <SafeAreaView style={styles.bottomControls}>
        {recordState === "idle" && analyzeStatus !== "error" && (
          <TouchableOpacity style={styles.recordButton} onPress={start}>
            <View style={styles.recordButtonInner} />
          </TouchableOpacity>
        )}

        {recordState === "recording" && (
          <TouchableOpacity style={styles.stopButton} onPress={handleStopEarly}>
            <View style={styles.stopButtonInner} />
          </TouchableOpacity>
        )}

        {analyzeStatus === "error" && (
          <TouchableOpacity style={styles.primaryButton} onPress={handleReset}>
            <Text style={styles.primaryButtonText}>Try Again</Text>
          </TouchableOpacity>
        )}
      </SafeAreaView>

      {isProcessing && (
        <UploadProgress
          status={analyzeStatus as "uploading" | "processing"}
          uploadProgress={uploadProgress}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  permissionContainer: { flex: 1, alignItems: "center", justifyContent: "center", padding: 32, gap: 16 },
  permissionTitle: { color: "#fff", fontSize: 22, fontWeight: "700", textAlign: "center" },
  permissionSubtitle: { color: "#999", fontSize: 15, textAlign: "center", lineHeight: 22 },
  ovalGuide: {
    position: "absolute", top: "12%", alignSelf: "center",
    width: 260, height: 340, borderRadius: 130,
    borderWidth: 3, borderColor: "#FF4D6Dbb", borderStyle: "dashed",
  },
  topOverlay: { position: "absolute", top: 0, left: 0, right: 0, alignItems: "center", paddingTop: 8 },
  instructionCard: {
    backgroundColor: "#0009", borderRadius: 12,
    paddingHorizontal: 20, paddingVertical: 12, margin: 16, alignItems: "center", gap: 4,
  },
  instructionTitle: { color: "#fff", fontSize: 18, fontWeight: "700" },
  instructionText: { color: "#ccc", fontSize: 13, textAlign: "center" },
  timerContainer: {
    flexDirection: "row", alignItems: "center", backgroundColor: "#0009",
    borderRadius: 20, paddingHorizontal: 16, paddingVertical: 8, margin: 16, gap: 8,
  },
  recordingDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: "#FF4D6D" },
  recordingDotMoving: { backgroundColor: "#FACC15" },
  timerContainerMoving: { borderWidth: 1, borderColor: "#FACC15" },
  motionWarning: {
    backgroundColor: "#FACC1522", borderRadius: 10, borderWidth: 1, borderColor: "#FACC1566",
    paddingHorizontal: 14, paddingVertical: 6, marginHorizontal: 16,
  },
  motionWarningText: { color: "#FACC15", fontSize: 12, textAlign: "center" },
  timerText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  progressBarBackground: { width: "80%", height: 4, backgroundColor: "#ffffff33", borderRadius: 2, overflow: "hidden" },
  progressBarFill: { height: 4, backgroundColor: "#FF4D6D", borderRadius: 2 },
  bottomOverlay: { position: "absolute", bottom: 120, left: 0, right: 0 },
  bottomControls: { position: "absolute", bottom: 0, left: 0, right: 0, alignItems: "center", paddingBottom: 40 },
  recordButton: { width: 80, height: 80, borderRadius: 40, borderWidth: 4, borderColor: "#fff", alignItems: "center", justifyContent: "center" },
  recordButtonInner: { width: 60, height: 60, borderRadius: 30, backgroundColor: "#FF4D6D" },
  stopButton: { width: 80, height: 80, borderRadius: 40, borderWidth: 4, borderColor: "#fff", alignItems: "center", justifyContent: "center" },
  stopButtonInner: { width: 30, height: 30, borderRadius: 4, backgroundColor: "#fff" },
  primaryButton: { backgroundColor: "#FF4D6D", paddingHorizontal: 32, paddingVertical: 14, borderRadius: 30 },
  primaryButtonText: { color: "#fff", fontWeight: "700", fontSize: 16 },
});
