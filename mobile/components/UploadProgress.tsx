import React, { useEffect, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  Animated,
  Easing,
  Dimensions,
} from "react-native";

interface UploadProgressProps {
  status: "compressing" | "uploading" | "processing";
  uploadProgress: number; // 0–1
}

const SCREEN_WIDTH = Dimensions.get("window").width;

export default function UploadProgress({ status, uploadProgress }: UploadProgressProps) {
  const spinAnim = useRef(new Animated.Value(0)).current;
  const barWidth = useRef(new Animated.Value(0)).current;

  // Spinner
  useEffect(() => {
    const spin = Animated.loop(
      Animated.timing(spinAnim, {
        toValue: 1,
        duration: 1000,
        easing: Easing.linear,
        useNativeDriver: true,
      })
    );
    spin.start();
    return () => spin.stop();
  }, [spinAnim]);

  // Upload progress bar
  useEffect(() => {
    const targetWidth =
      status === "processing" ? SCREEN_WIDTH - 48 : (SCREEN_WIDTH - 48) * uploadProgress;
    Animated.timing(barWidth, {
      toValue: targetWidth,
      duration: 300,
      useNativeDriver: false,
    }).start();
  }, [uploadProgress, status, barWidth]);

  const rotate = spinAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });

  return (
    <View style={styles.overlay}>
      <Animated.View style={[styles.spinner, { transform: [{ rotate }] }]} />
      <Text style={styles.title}>
        {status === "compressing"
          ? "Compressing video…"
          : status === "uploading"
          ? "Uploading video…"
          : "Analyzing heart rate…"}
      </Text>
      <Text style={styles.subtitle}>
        {status === "compressing"
          ? "Reducing file size for faster upload…"
          : status === "uploading"
          ? `${Math.round(uploadProgress * 100)}% uploaded`
          : "This takes ~20 seconds. Stay still!"}
      </Text>
      {/* Progress bar */}
      <View style={styles.barBackground}>
        <Animated.View style={[styles.barFill, { width: barWidth }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#0a0a0aee",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 50,
    gap: 12,
  },
  spinner: {
    width: 48,
    height: 48,
    borderRadius: 24,
    borderWidth: 4,
    borderColor: "#FF4D6D22",
    borderTopColor: "#FF4D6D",
    marginBottom: 8,
  },
  title: {
    color: "#fff",
    fontSize: 20,
    fontWeight: "700",
  },
  subtitle: {
    color: "#999",
    fontSize: 14,
    textAlign: "center",
    paddingHorizontal: 32,
  },
  barBackground: {
    width: SCREEN_WIDTH - 48,
    height: 4,
    backgroundColor: "#333",
    borderRadius: 2,
    marginTop: 8,
    overflow: "hidden",
  },
  barFill: {
    height: 4,
    backgroundColor: "#FF4D6D",
    borderRadius: 2,
  },
});
