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

const SEX_OPTIONS = ["Male", "Female", "Other"];
const STRESS_OPTIONS = ["Low", "Medium", "High"];
const ACTIVITY_CHIPS = ["Resting", "Light walk", "Moderate exercise", "Intense workout"];
const CAFFEINE_OPTIONS = ["No", "Yes"];

function ChipGroup({
  label,
  hint,
  options,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <View style={{ gap: 8 }}>
      <Text style={chipStyles.label}>{label}</Text>
      {hint ? <Text style={chipStyles.hint}>{hint}</Text> : null}
      <View style={chipStyles.row}>
        {options.map((opt) => (
          <TouchableOpacity
            key={opt}
            style={[chipStyles.chip, value === opt && chipStyles.chipActive]}
            onPress={() => onChange(value === opt ? "" : opt)}
          >
            <Text style={[chipStyles.chipText, value === opt && chipStyles.chipTextActive]}>
              {opt}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const chipStyles = StyleSheet.create({
  label: { color: "#ccc", fontSize: 14, fontWeight: "600" },
  hint: { color: "#666", fontSize: 12, marginTop: -4 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: 20, borderWidth: 1, borderColor: "#2a2a2a",
    backgroundColor: "#1e1e1e",
  },
  chipActive: { borderColor: "#FF4D6D", backgroundColor: "#FF4D6D22" },
  chipText: { color: "#777", fontSize: 13, fontWeight: "500" },
  chipTextActive: { color: "#FF4D6D", fontWeight: "700" },
});

export default function HomeScreen() {
  const [age, setAge] = useState("");
  const [sex, setSex] = useState("");
  const [activityChip, setActivityChip] = useState("");
  const [activityNote, setActivityNote] = useState("");
  const [stress, setStress] = useState("");
  const [caffeine, setCaffeine] = useState("");
  const [medications, setMedications] = useState("");

  const canScan = age.trim().length > 0 && parseInt(age) > 0 && parseInt(age) < 130;

  const handleStartScan = () => {
    const activitySummary = [activityChip, activityNote.trim()].filter(Boolean).join(" — ");
    router.push({
      pathname: "/scan",
      params: {
        age: age.trim(),
        sex,
        activity: activitySummary,
        stress,
        caffeine,
        medications: medications.trim(),
      },
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

          {/* Tips for accurate reading */}
          <View style={styles.tipsCard}>
            <Text style={styles.tipsTitle}>For best accuracy</Text>
            <View style={styles.tipsRow}>
              <Text style={styles.tipIcon}>💡</Text>
              <Text style={styles.tipText}>Good, even lighting on your face (avoid backlighting)</Text>
            </View>
            <View style={styles.tipsRow}>
              <Text style={styles.tipIcon}>🧘</Text>
              <Text style={styles.tipText}>Sit still — any movement reduces accuracy</Text>
            </View>
            <View style={styles.tipsRow}>
              <Text style={styles.tipIcon}>😐</Text>
              <Text style={styles.tipText}>Keep a neutral expression throughout the scan</Text>
            </View>
            <View style={styles.tipsRow}>
              <Text style={styles.tipIcon}>📱</Text>
              <Text style={styles.tipText}>Hold phone at eye level, face fully in the oval</Text>
            </View>
          </View>

          {/* Personal details */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Personal details</Text>

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
            {!canScan && age.length > 0 && (
              <Text style={styles.validationHint}>Please enter a valid age</Text>
            )}

            <ChipGroup
              label="Sex"
              options={SEX_OPTIONS}
              value={sex}
              onChange={setSex}
            />
          </View>

          {/* Pre-scan context */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Right now</Text>

            <ChipGroup
              label="Activity in the last 30 minutes"
              options={ACTIVITY_CHIPS}
              value={activityChip}
              onChange={setActivityChip}
            />

            <Text style={styles.label}>Additional activity notes</Text>
            <TextInput
              style={[styles.input, styles.inputMultiline]}
              placeholder="e.g. just finished yoga, been sitting for 2 hours..."
              placeholderTextColor="#555"
              value={activityNote}
              onChangeText={setActivityNote}
              multiline
              numberOfLines={2}
              maxLength={150}
              textAlignVertical="top"
            />

            <ChipGroup
              label="Stress level"
              options={STRESS_OPTIONS}
              value={stress}
              onChange={setStress}
            />

            <ChipGroup
              label="Caffeine today?"
              hint="Coffee, tea, energy drinks"
              options={CAFFEINE_OPTIONS}
              value={caffeine}
              onChange={setCaffeine}
            />
          </View>

          {/* Health context */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Health context</Text>
            <Text style={styles.label}>Medications or conditions</Text>
            <Text style={styles.labelHint}>
              e.g. beta-blockers, thyroid medication, arrhythmia — helps interpret results
            </Text>
            <TextInput
              style={[styles.input, styles.inputMultiline]}
              placeholder="Optional — leave blank if none"
              placeholderTextColor="#555"
              value={medications}
              onChangeText={setMedications}
              multiline
              numberOfLines={2}
              maxLength={200}
              textAlignVertical="top"
            />
          </View>

          {/* How it works */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>How it works</Text>
            <View style={styles.stepRow}>
              <View style={styles.stepBadge}><Text style={styles.stepNum}>1</Text></View>
              <Text style={styles.stepText}>Your face is recorded for 60 seconds</Text>
            </View>
            <View style={styles.stepRow}>
              <View style={styles.stepBadge}><Text style={styles.stepNum}>2</Text></View>
              <Text style={styles.stepText}>AI detects subtle colour changes from blood flow (rPPG)</Text>
            </View>
            <View style={styles.stepRow}>
              <View style={styles.stepBadge}><Text style={styles.stepNum}>3</Text></View>
              <Text style={styles.stepText}>Heart rate + waveform extracted from the signal</Text>
            </View>
            <View style={styles.stepRow}>
              <View style={styles.stepBadge}><Text style={styles.stepNum}>4</Text></View>
              <Text style={styles.stepText}>Results shown with confidence score</Text>
            </View>
          </View>

          {/* Scan button */}
          <TouchableOpacity
            style={[styles.scanButton, !canScan && styles.scanButtonDisabled]}
            onPress={handleStartScan}
            disabled={!canScan}
          >
            <Text style={styles.scanButtonText}>Start Scan</Text>
          </TouchableOpacity>

          <Text style={styles.disclaimer}>
            Not a medical device. Results are for informational purposes only.{"\n"}
            Consult a healthcare professional for medical advice.
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
  tipsCard: {
    backgroundColor: "#0d1a14",
    borderRadius: 16,
    padding: 20,
    gap: 10,
    borderWidth: 1,
    borderColor: "#1a3a28",
  },
  tipsTitle: { color: "#4ADE80", fontSize: 14, fontWeight: "700", marginBottom: 2 },
  tipsRow: { flexDirection: "row", gap: 10, alignItems: "flex-start" },
  tipIcon: { fontSize: 16, width: 24 },
  tipText: { color: "#aaa", fontSize: 13, flex: 1, lineHeight: 18 },
  card: { backgroundColor: "#141414", borderRadius: 16, padding: 20, gap: 12 },
  cardTitle: { color: "#fff", fontSize: 16, fontWeight: "700", marginBottom: 2 },
  stepRow: { flexDirection: "row", alignItems: "flex-start", gap: 12 },
  stepBadge: {
    width: 26, height: 26, borderRadius: 13,
    backgroundColor: "#FF4D6D22", borderWidth: 1, borderColor: "#FF4D6D",
    alignItems: "center", justifyContent: "center", marginTop: 1,
  },
  stepNum: { color: "#FF4D6D", fontSize: 13, fontWeight: "700" },
  stepText: { color: "#bbb", fontSize: 14, flex: 1, lineHeight: 20 },
  label: { color: "#ccc", fontSize: 14, fontWeight: "600" },
  labelHint: { color: "#666", fontSize: 12, marginTop: -8, lineHeight: 18 },
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
  inputMultiline: { minHeight: 72, paddingTop: 12 },
  scanButton: {
    backgroundColor: "#FF4D6D",
    paddingVertical: 18,
    borderRadius: 30,
    alignItems: "center",
    marginTop: 4,
  },
  scanButtonDisabled: { backgroundColor: "#FF4D6D44" },
  scanButtonText: { color: "#fff", fontSize: 18, fontWeight: "800", letterSpacing: 0.5 },
  validationHint: { color: "#FF4D6D", fontSize: 12, marginTop: -6 },
  disclaimer: { color: "#444", fontSize: 12, textAlign: "center", lineHeight: 18 },
});
