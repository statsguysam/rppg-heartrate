import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  Alert,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import { router } from "expo-router";

import { useVideoRecording } from "../../hooks/useVideoRecording";
import { useAnalyze } from "../../hooks/useAnalyze";
import UploadProgress from "../../components/UploadProgress";
import ErrorBanner from "../../components/ErrorBanner";
import { RECORDING_DURATION_MS, MIN_DURATION_WARNING_MS } from "../../constants/config";

export default function RecordScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const { status: analyzeStatus, uploadProgress, result, error, analyze, reset: resetAnalyze } = useAnalyze();

  const handleRecordingComplete = async (uri: string) => {
    await analyze(uri);
  };

  const handleRecordingError = (message: string) => {
    Alert.alert("Recording Failed", message, [{ text: "OK" }]);
  };

  const { cameraRef, state: recordState, elapsed, start, stop, reset: resetRecording } =
    useVideoRecording(handleRecordingComplete, handleRecordingError);

  // Navigate to result screen when done, show Alert on error
  useEffect(() => {
    if (analyzeStatus === "done" && result) {
      router.push({
        pathname: "/result",
        params: {
          bpm: result.bpm.toString(),
          confidence: result.confidence.toString(),
          waveform: JSON.stringify(result.waveform),
          waveform_fps: result.waveform_fps.toString(),
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
        `Please record for at least 50 seconds for an accurate reading. Current: ${elapsed}s`,
        [
          { text: "Keep Recording", style: "cancel" },
          { text: "Stop Anyway", style: "destructive", onPress: stop },
        ]
      );
    } else {
      stop();
    }
  };

  if (!permission) return <View style={styles.container} />;

  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.permissionContainer}>
          <Text style={styles.permissionTitle}>Camera Permission Required</Text>
          <Text style={styles.permissionSubtitle}>
            Heart Rate Monitor needs camera access to measure your heart rate from your face.
          </Text>
          <TouchableOpacity style={styles.primaryButton} onPress={requestPermission}>
            <Text style={styles.primaryButtonText}>Grant Permission</Text>
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
      {/* Camera preview */}
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFillObject}
        facing="front"
        mode="video"
      />

      {/* Face guide oval */}
      <View style={styles.ovalGuide} />

      {/* Top instruction */}
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

      {/* Recording timer overlay */}
      {recordState === "recording" && (
        <SafeAreaView style={styles.topOverlay}>
          <View style={styles.timerContainer}>
            <View style={styles.recordingDot} />
            <Text style={styles.timerText}>{countdown}s remaining</Text>
          </View>
          {/* Progress arc (simple bar) */}
          <View style={styles.progressBarBackground}>
            <View style={[styles.progressBarFill, { width: `${progress * 100}%` }]} />
          </View>
        </SafeAreaView>
      )}

      {/* Error banner */}
      {analyzeStatus === "error" && error && (
        <SafeAreaView style={styles.bottomOverlay}>
          <ErrorBanner message={error} onRetry={handleReset} />
        </SafeAreaView>
      )}

      {/* Bottom controls */}
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

      {/* Processing overlay — shown on top of everything */}
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
  container: {
    flex: 1,
    backgroundColor: "#000",
  },
  permissionContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
    gap: 16,
  },
  permissionTitle: {
    color: "#fff",
    fontSize: 22,
    fontWeight: "700",
    textAlign: "center",
  },
  permissionSubtitle: {
    color: "#999",
    fontSize: 15,
    textAlign: "center",
    lineHeight: 22,
  },
  ovalGuide: {
    position: "absolute",
    top: "18%",
    alignSelf: "center",
    width: 200,
    height: 270,
    borderRadius: 100,
    borderWidth: 2,
    borderColor: "#FF4D6D88",
    borderStyle: "dashed",
  },
  topOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    alignItems: "center",
    paddingTop: 8,
  },
  instructionCard: {
    backgroundColor: "#0009",
    borderRadius: 12,
    paddingHorizontal: 20,
    paddingVertical: 12,
    margin: 16,
    alignItems: "center",
    gap: 4,
  },
  instructionTitle: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "700",
  },
  instructionText: {
    color: "#ccc",
    fontSize: 13,
    textAlign: "center",
  },
  timerContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#0009",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
    margin: 16,
    gap: 8,
  },
  recordingDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: "#FF4D6D",
  },
  timerText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  progressBarBackground: {
    width: "80%",
    height: 4,
    backgroundColor: "#ffffff33",
    borderRadius: 2,
    overflow: "hidden",
  },
  progressBarFill: {
    height: 4,
    backgroundColor: "#FF4D6D",
    borderRadius: 2,
  },
  bottomOverlay: {
    position: "absolute",
    bottom: 120,
    left: 0,
    right: 0,
  },
  bottomControls: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    alignItems: "center",
    paddingBottom: 40,
  },
  recordButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 4,
    borderColor: "#fff",
    alignItems: "center",
    justifyContent: "center",
  },
  recordButtonInner: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: "#FF4D6D",
  },
  stopButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 4,
    borderColor: "#fff",
    alignItems: "center",
    justifyContent: "center",
  },
  stopButtonInner: {
    width: 30,
    height: 30,
    borderRadius: 4,
    backgroundColor: "#fff",
  },
  primaryButton: {
    backgroundColor: "#FF4D6D",
    paddingHorizontal: 32,
    paddingVertical: 14,
    borderRadius: 30,
  },
  primaryButtonText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 16,
  },
});
