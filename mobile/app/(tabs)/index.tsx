import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { router } from "expo-router";

export default function HomeScreen() {
  const [age, setAge] = useState("");
  const [activity, setActivity] = useState("");

  const canScan = age.trim().length > 0 && parseInt(age) > 0 && parseInt(age) < 130;

  const handleStartScan = () => {
    router.push({
      pathname: "/scan",
      params: { age: age.trim(), activity: activity.trim() },
    });
  };

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">

          {/* Header */}
          <View style={styles.header}>
            <View style={styles.heartIcon}>
              <Text style={styles.heartEmoji}>♥</Text>
            </View>
            <Text style={styles.title}>Heart Rate Monitor</Text>
            <Text style={styles.subtitle}>
              Measure your heart rate using your phone's front camera
            </Text>
          </View>

          {/* How it works */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>How it works</Text>
            <View style={styles.stepRow}>
              <View style={styles.stepBadge}><Text style={styles.stepNum}>1</Text></View>
              <Text style={styles.stepText}>Fill in your details below</Text>
            </View>
            <View style={styles.stepRow}>
              <View style={styles.stepBadge}><Text style={styles.stepNum}>2</Text></View>
              <Text style={styles.stepText}>Position your face in the oval guide</Text>
            </View>
            <View style={styles.stepRow}>
              <View style={styles.stepBadge}><Text style={styles.stepNum}>3</Text></View>
              <Text style={styles.stepText}>Stay still for 60 seconds while we scan</Text>
            </View>
            <View style={styles.stepRow}>
              <View style={styles.stepBadge}><Text style={styles.stepNum}>4</Text></View>
              <Text style={styles.stepText}>Get your heart rate result instantly</Text>
            </View>
          </View>

          {/* Input form */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Before you scan</Text>

            <Text style={styles.label}>Age <Text style={styles.required}>*</Text></Text>
            <TextInput
              style={styles.input}
              placeholder="Enter your age"
              placeholderTextColor="#555"
              keyboardType="number-pad"
              value={age}
              onChangeText={setAge}
              maxLength={3}
              returnKeyType="next"
            />

            <Text style={styles.label}>Physical Activity</Text>
            <Text style={styles.labelHint}>What were you doing before this scan?</Text>
            <TextInput
              style={[styles.input, styles.inputMultiline]}
              placeholder="e.g. resting, just finished a 30 min walk, light stretching..."
              placeholderTextColor="#555"
              value={activity}
              onChangeText={setActivity}
              multiline
              numberOfLines={3}
              maxLength={200}
              textAlignVertical="top"
            />
            <Text style={styles.charCount}>{activity.length}/200</Text>
          </View>

          {/* Scan button */}
          <TouchableOpacity
            style={[styles.scanButton, !canScan && styles.scanButtonDisabled]}
            onPress={handleStartScan}
            disabled={!canScan}
          >
            <Text style={styles.scanButtonText}>Start Scan</Text>
          </TouchableOpacity>

          {!canScan && age.length > 0 && (
            <Text style={styles.validationHint}>Please enter a valid age to continue</Text>
          )}

          <Text style={styles.disclaimer}>
            Not a medical device. For informational use only.
          </Text>

        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#0a0a0a" },
  container: { padding: 24, gap: 20, paddingBottom: 40 },
  header: { alignItems: "center", gap: 12, paddingTop: 16 },
  heartIcon: {
    width: 72, height: 72, borderRadius: 36,
    backgroundColor: "#FF4D6D22",
    alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: "#FF4D6D44",
  },
  heartEmoji: { fontSize: 32 },
  title: { color: "#fff", fontSize: 26, fontWeight: "800", textAlign: "center" },
  subtitle: { color: "#888", fontSize: 14, textAlign: "center", lineHeight: 20 },
  card: {
    backgroundColor: "#141414",
    borderRadius: 16,
    padding: 20,
    gap: 10,
  },
  cardTitle: { color: "#fff", fontSize: 16, fontWeight: "700", marginBottom: 4 },
  stepRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  stepBadge: {
    width: 26, height: 26, borderRadius: 13,
    backgroundColor: "#FF4D6D22", borderWidth: 1, borderColor: "#FF4D6D",
    alignItems: "center", justifyContent: "center",
  },
  stepNum: { color: "#FF4D6D", fontSize: 13, fontWeight: "700" },
  stepText: { color: "#bbb", fontSize: 14, flex: 1 },
  label: { color: "#ccc", fontSize: 14, fontWeight: "600" },
  labelHint: { color: "#666", fontSize: 12, marginTop: -6 },
  required: { color: "#FF4D6D" },
  input: {
    backgroundColor: "#1e1e1e",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#2a2a2a",
    color: "#fff",
    fontSize: 15,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  inputMultiline: { minHeight: 80, paddingTop: 12 },
  charCount: { color: "#444", fontSize: 11, textAlign: "right", marginTop: -4 },
  scanButton: {
    backgroundColor: "#FF4D6D",
    paddingVertical: 18,
    borderRadius: 30,
    alignItems: "center",
    marginTop: 4,
  },
  scanButtonDisabled: { backgroundColor: "#FF4D6D55" },
  scanButtonText: { color: "#fff", fontSize: 18, fontWeight: "800", letterSpacing: 0.5 },
  validationHint: { color: "#FF4D6D", fontSize: 13, textAlign: "center", marginTop: -12 },
  disclaimer: { color: "#444", fontSize: 12, textAlign: "center" },
});
