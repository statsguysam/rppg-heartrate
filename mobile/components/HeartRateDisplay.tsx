import React, { useEffect, useRef } from "react";
import { View, Text, Animated, StyleSheet } from "react-native";

interface HeartRateDisplayProps {
  bpm: number;
  confidence: number; // 0–1
}

function confidenceLabel(c: number): { label: string; color: string } {
  if (c >= 0.7) return { label: "High Confidence", color: "#4ADE80" };
  if (c >= 0.4) return { label: "Medium Confidence", color: "#FACC15" };
  return { label: "Low Confidence", color: "#F87171" };
}

export default function HeartRateDisplay({ bpm, confidence }: HeartRateDisplayProps) {
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const { label, color } = confidenceLabel(confidence);

  // Animate pulse ring at measured BPM rate
  useEffect(() => {
    const intervalMs = (60 / bpm) * 1000;
    const pulse = Animated.sequence([
      Animated.timing(pulseAnim, {
        toValue: 1.25,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(pulseAnim, {
        toValue: 1,
        duration: intervalMs - 200,
        useNativeDriver: true,
      }),
    ]);
    const loop = Animated.loop(pulse);
    loop.start();
    return () => loop.stop();
  }, [bpm, pulseAnim]);

  return (
    <View style={styles.container}>
      {/* Pulse ring */}
      <Animated.View
        style={[
          styles.ring,
          { transform: [{ scale: pulseAnim }] },
        ]}
      />
      {/* BPM number */}
      <View style={styles.bpmContainer}>
        <Text style={styles.bpmNumber}>{bpm.toFixed(0)}</Text>
        <Text style={styles.bpmUnit}>BPM</Text>
      </View>
      {/* Confidence badge */}
      <View style={[styles.badge, { borderColor: color }]}>
        <View style={[styles.badgeDot, { backgroundColor: color }]} />
        <Text style={[styles.badgeText, { color }]}>{label}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 20,
  },
  ring: {
    position: "absolute",
    width: 160,
    height: 160,
    borderRadius: 80,
    borderWidth: 3,
    borderColor: "#FF4D6D44",
  },
  bpmContainer: {
    width: 160,
    height: 160,
    borderRadius: 80,
    borderWidth: 3,
    borderColor: "#FF4D6D",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#1a0a0f",
  },
  bpmNumber: {
    fontSize: 56,
    fontWeight: "800",
    color: "#FF4D6D",
    lineHeight: 60,
  },
  bpmUnit: {
    fontSize: 16,
    fontWeight: "600",
    color: "#FF4D6D99",
    letterSpacing: 3,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 6,
    marginTop: 20,
    gap: 6,
  },
  badgeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  badgeText: {
    fontSize: 13,
    fontWeight: "600",
  },
});
