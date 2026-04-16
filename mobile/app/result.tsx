import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { saveScan } from "../services/api";
import {
  applyCalibration,
  computeOffsets,
  isCalibrationStale,
  loadCalibration,
  saveCalibration,
  type BPCalibration,
} from "../services/calibration";

import HeartRateDisplay from "../components/HeartRateDisplay";
import WaveformChart from "../components/WaveformChart";

export default function ResultScreen() {
  const {
    bpm, confidence, waveform, waveform_fps,
    age, sex, activity, stress, caffeine, medications, video_url,
    sbp, dbp, bp_confidence,
    calibration, cuff_sbp, cuff_dbp, return_to,
  } = useLocalSearchParams<{
    bpm: string; confidence: string; waveform: string; waveform_fps: string;
    age: string; sex: string; activity: string; stress: string; caffeine: string; medications: string; video_url: string;
    sbp?: string; dbp?: string; bp_confidence?: string;
    calibration?: string; cuff_sbp?: string; cuff_dbp?: string; return_to?: string;
  }>();

  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [cal, setCal] = useState<BPCalibration | null>(null);

  const bpmVal = parseFloat(bpm ?? "0");
  const confVal = parseFloat(confidence ?? "0");
  const waveformData: number[] = waveform ? JSON.parse(waveform) : [];

  const rawSbp = sbp ? parseFloat(sbp) : null;
  const rawDbp = dbp ? parseFloat(dbp) : null;
  const bpConf = bp_confidence ? parseFloat(bp_confidence) : null;
  const isCalibrationRun = calibration === "1" && cuff_sbp && cuff_dbp;

  // Save to local history only on load
  useEffect(() => {
    if (!bpmVal) return;
    const save = async () => {
      try {
        const existing = await AsyncStorage.getItem("hr_history");
        const history = existing ? JSON.parse(existing) : [];
        history.unshift({
          id: Date.now().toString(),
          bpm: bpmVal,
          confidence: confVal,
          age: age ? parseInt(age) : null,
          sex: sex || null,
          activity: activity || null,
          stress: stress || null,
          caffeine: caffeine || null,
          medications: medications || null,
          timestamp: new Date().toISOString(),
        });
        await AsyncStorage.setItem("hr_history", JSON.stringify(history.slice(0, 50)));
      } catch { }
    };
    save();
  }, []);

  // Calibration pairing. If this scan came from the calibrate flow and the
  // backend returned a raw BP estimate, compute & persist offsets, then
  // bounce the user back where they came from.
  useEffect(() => {
    if (!isCalibrationRun || rawSbp == null || rawDbp == null) return;
    const run = async () => {
      const offsets = computeOffsets(
        parseInt(cuff_sbp!, 10),
        parseInt(cuff_dbp!, 10),
        rawSbp,
        rawDbp,
      );
      await saveCalibration(offsets);
      Alert.alert(
        "Calibration saved",
        `Offset locked in: SBP ${offsets.sbp_offset >= 0 ? "+" : ""}${Math.round(offsets.sbp_offset)} / DBP ${offsets.dbp_offset >= 0 ? "+" : ""}${Math.round(offsets.dbp_offset)} mmHg. Future scans will use this.`,
        [{ text: "OK", onPress: () => router.replace((return_to as any) || "/") }]
      );
    };
    run();
  }, [isCalibrationRun, rawSbp, rawDbp]);

  // If the calibration scan itself failed to produce a BP estimate, tell
  // the user clearly instead of silently losing the flow.
  useEffect(() => {
    if (!isCalibrationRun) return;
    if (rawSbp != null && rawDbp != null) return;
    Alert.alert(
      "Calibration incomplete",
      "We couldn't extract a clean pulse waveform from that scan. Try again in better lighting, staying very still.",
      [{ text: "OK", onPress: () => router.replace("/calibrate") }]
    );
  }, [isCalibrationRun, rawSbp, rawDbp]);

  // Load stored calibration once so we can display calibrated BP for normal scans.
  useEffect(() => {
    loadCalibration().then(setCal);
  }, []);

  const calibrated = applyCalibration(rawSbp, rawDbp, cal);
  const calStale = isCalibrationStale(cal);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await saveScan({
        bpm: bpmVal,
        confidence: confVal,
        age: age ? parseInt(age) : undefined,
        sex: sex || undefined,
        activity: activity || undefined,
        stress: stress || undefined,
        caffeine: caffeine || undefined,
        medications: medications || undefined,
        video_url: video_url || undefined,
        comment: comment.trim() || undefined,
      });
      setSubmitted(true);
    } catch {
      Alert.alert("Error", "Failed to save. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const bpmCategory = bpmVal < 60 ? "Bradycardia" : bpmVal > 100 ? "Tachycardia" : "Normal";
  const bpmCategoryColor = bpmVal < 60 || bpmVal > 100 ? "#FACC15" : "#4ADE80";

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : "height"}>
      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
        {/* Context card */}
        {(age || sex || activity || stress || caffeine || medications) && (
          <View style={styles.contextCard}>
            <Text style={styles.contextTitle}>Scan context</Text>
            <View style={styles.contextGrid}>
              {age ? <View style={styles.contextItem}><Text style={styles.contextKey}>Age</Text><Text style={styles.contextVal}>{age}</Text></View> : null}
              {sex ? <View style={styles.contextItem}><Text style={styles.contextKey}>Sex</Text><Text style={styles.contextVal}>{sex}</Text></View> : null}
              {stress ? <View style={styles.contextItem}><Text style={styles.contextKey}>Stress</Text><Text style={styles.contextVal}>{stress}</Text></View> : null}
              {caffeine ? <View style={styles.contextItem}><Text style={styles.contextKey}>Caffeine</Text><Text style={styles.contextVal}>{caffeine}</Text></View> : null}
            </View>
            {activity ? <Text style={styles.contextActivity}>Activity: {activity}</Text> : null}
            {medications ? <Text style={styles.contextActivity}>Medications/conditions: {medications}</Text> : null}
          </View>
        )}

        {/* Heart Rate Display */}
        <HeartRateDisplay bpm={bpmVal} confidence={confVal} />

        {/* Category */}
        <View style={[styles.categoryBadge, { borderColor: bpmCategoryColor }]}>
          <Text style={[styles.categoryText, { color: bpmCategoryColor }]}>
            {bpmCategory} Range
          </Text>
        </View>

        {/* Blood pressure — only shown once calibrated. Uncalibrated BP is
            too noisy to display as a number; we nudge the user to calibrate. */}
        {calibrated.sbp != null && calibrated.dbp != null && calibrated.calibrated && !isCalibrationRun && (
          <View style={styles.bpCard}>
            <Text style={styles.cardTitle}>Blood Pressure</Text>
            <View style={styles.bpRow}>
              <Text style={styles.bpNumber}>{calibrated.sbp}</Text>
              <Text style={styles.bpSlash}>/</Text>
              <Text style={styles.bpNumber}>{calibrated.dbp}</Text>
              <Text style={styles.bpUnit}>mmHg</Text>
            </View>
            {bpConf != null && (
              <Text style={styles.bpSubtle}>
                Signal confidence {Math.round(bpConf * 100)}% · wellness estimate, not a medical measurement
              </Text>
            )}
            {calStale && (
              <TouchableOpacity style={styles.calRefresh} onPress={() => router.push("/calibrate")}>
                <Text style={styles.calRefreshText}>⟳ Re-calibrate (last reading &gt; 14 days ago)</Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* Uncalibrated-but-have-model-output nudge */}
        {rawSbp != null && rawDbp != null && !calibrated.calibrated && !isCalibrationRun && (
          <TouchableOpacity style={styles.bpCalibratePrompt} onPress={() => router.push("/calibrate")}>
            <Text style={styles.bpCalibratePromptTitle}>Enable Blood Pressure</Text>
            <Text style={styles.bpCalibratePromptText}>
              Calibrate once with a cuff reading to show your BP on future scans.
            </Text>
          </TouchableOpacity>
        )}

        {/* Reference ranges */}
        <View style={styles.infoCard}>
          <Text style={styles.cardTitle}>Reference Ranges</Text>
          <View style={styles.rangeRow}>
            <Text style={styles.rangeLabel}>Bradycardia</Text>
            <Text style={styles.rangeValue}>&lt; 60 BPM</Text>
          </View>
          <View style={styles.rangeRow}>
            <Text style={[styles.rangeLabel, { color: "#4ADE80" }]}>Normal</Text>
            <Text style={[styles.rangeValue, { color: "#4ADE80" }]}>60–100 BPM</Text>
          </View>
          <View style={styles.rangeRow}>
            <Text style={styles.rangeLabel}>Tachycardia</Text>
            <Text style={styles.rangeValue}>&gt; 100 BPM</Text>
          </View>
        </View>

        {/* Waveform */}
        {waveformData.length > 0 && (
          <View style={styles.waveformSection}>
            <Text style={styles.cardTitle}>rPPG Signal</Text>
            <Text style={styles.cardSubtitle}>
              Blood volume pulse waveform detected from your face
            </Text>
            <WaveformChart data={waveformData} height={130} />
          </View>
        )}

        {/* Disclaimer */}
        <View style={styles.disclaimer}>
          <Text style={styles.disclaimerText}>
            ⚕ This is not a medical device. Results are for informational purposes only.
            Consult a healthcare professional for medical advice.
          </Text>
        </View>

        {/* Comment box */}
        {!submitted ? (
          <View style={styles.commentCard}>
            <Text style={styles.commentTitle}>How do you feel?</Text>
            <Text style={styles.commentHint}>Add any notes about how you're feeling, symptoms, or anything relevant.</Text>
            <TextInput
              style={styles.commentInput}
              placeholder="e.g. Feeling relaxed, slight headache, just woke up..."
              placeholderTextColor="#555"
              value={comment}
              onChangeText={setComment}
              multiline
              numberOfLines={3}
              maxLength={300}
              textAlignVertical="top"
            />
            <Text style={styles.charCount}>{comment.length}/300</Text>
            <TouchableOpacity
              style={[styles.submitButton, submitting && styles.submitButtonDisabled]}
              onPress={handleSubmit}
              disabled={submitting}
            >
              <Text style={styles.submitButtonText}>
                {submitting ? "Saving..." : "Submit & Save"}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.scanAgainOutline} onPress={() => router.replace("/")}>
              <Text style={styles.scanAgainOutlineText}>Scan Again</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.submittedCard}>
            <Text style={styles.submittedIcon}>✓</Text>
            <Text style={styles.submittedText}>Saved successfully!</Text>
            <TouchableOpacity style={styles.measureAgainButton} onPress={() => router.replace("/")}>
              <Text style={styles.measureAgainText}>Scan Again</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#0a0a0a",
  },
  container: {
    padding: 24,
    gap: 20,
    alignItems: "center",
  },
  contextCard: {
    width: "100%",
    backgroundColor: "#141414",
    borderRadius: 12,
    padding: 16,
    gap: 10,
  },
  contextTitle: { color: "#fff", fontSize: 14, fontWeight: "700" },
  contextGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  contextItem: {
    backgroundColor: "#1e1e1e",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    minWidth: 80,
  },
  contextKey: { color: "#666", fontSize: 11, fontWeight: "600" },
  contextVal: { color: "#ccc", fontSize: 13, fontWeight: "600", marginTop: 2 },
  contextActivity: { color: "#888", fontSize: 12, lineHeight: 18 },
  contextText: { color: "#888", fontSize: 13 },
  categoryBadge: {
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 6,
  },
  categoryText: {
    fontSize: 14,
    fontWeight: "600",
    letterSpacing: 1,
  },
  infoCard: {
    width: "100%",
    backgroundColor: "#141414",
    borderRadius: 16,
    padding: 16,
    gap: 10,
  },
  cardTitle: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 4,
  },
  cardSubtitle: {
    color: "#666",
    fontSize: 13,
    marginBottom: 8,
  },
  rangeRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  rangeLabel: {
    color: "#aaa",
    fontSize: 14,
  },
  rangeValue: {
    color: "#aaa",
    fontSize: 14,
    fontWeight: "600",
  },
  waveformSection: {
    width: "100%",
    backgroundColor: "#141414",
    borderRadius: 16,
    padding: 16,
    gap: 8,
  },
  disclaimer: {
    backgroundColor: "#1a1a1a",
    borderRadius: 12,
    padding: 14,
  },
  disclaimerText: {
    color: "#666",
    fontSize: 12,
    lineHeight: 18,
    textAlign: "center",
  },
  measureAgainButton: {
    backgroundColor: "#FF4D6D",
    paddingHorizontal: 40,
    paddingVertical: 16,
    borderRadius: 30,
    marginBottom: 20,
  },
  measureAgainText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  commentCard: {
    width: "100%", backgroundColor: "#141414",
    borderRadius: 16, padding: 20, gap: 10,
  },
  commentTitle: { color: "#fff", fontSize: 16, fontWeight: "700" },
  commentHint: { color: "#666", fontSize: 13, lineHeight: 18 },
  commentInput: {
    backgroundColor: "#1e1e1e", borderRadius: 10,
    borderWidth: 1, borderColor: "#2a2a2a",
    color: "#fff", fontSize: 14,
    paddingHorizontal: 14, paddingVertical: 12,
    minHeight: 90,
  },
  charCount: { color: "#444", fontSize: 11, textAlign: "right", marginTop: -4 },
  submitButton: {
    backgroundColor: "#FF4D6D", paddingVertical: 16,
    borderRadius: 30, alignItems: "center",
  },
  submitButtonDisabled: { backgroundColor: "#FF4D6D55" },
  submitButtonText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  scanAgainOutline: {
    borderWidth: 1, borderColor: "#333",
    paddingVertical: 14, borderRadius: 30, alignItems: "center",
  },
  scanAgainOutlineText: { color: "#888", fontWeight: "600", fontSize: 15 },
  submittedCard: {
    width: "100%", alignItems: "center", gap: 12,
    backgroundColor: "#0d1a14", borderRadius: 16, padding: 24,
    borderWidth: 1, borderColor: "#1a3a28", marginBottom: 20,
  },
  submittedIcon: { fontSize: 36, color: "#4ADE80" },
  submittedText: { color: "#4ADE80", fontSize: 16, fontWeight: "700" },
  bpCard: {
    width: "100%", backgroundColor: "#141414", borderRadius: 16,
    padding: 20, gap: 8, alignItems: "center",
  },
  bpRow: { flexDirection: "row", alignItems: "baseline", gap: 6 },
  bpNumber: { color: "#FF4D6D", fontSize: 44, fontWeight: "800", lineHeight: 48 },
  bpSlash: { color: "#FF4D6D99", fontSize: 32, fontWeight: "700" },
  bpUnit: { color: "#FF4D6D99", fontSize: 13, fontWeight: "600", letterSpacing: 1, marginLeft: 6 },
  bpSubtle: { color: "#666", fontSize: 12, textAlign: "center", paddingHorizontal: 8 },
  calRefresh: { marginTop: 6 },
  calRefreshText: { color: "#FACC15", fontSize: 12, fontWeight: "600" },
  bpCalibratePrompt: {
    width: "100%", backgroundColor: "#14141e", borderRadius: 14,
    padding: 16, borderWidth: 1, borderColor: "#2a2a3a", gap: 4,
  },
  bpCalibratePromptTitle: { color: "#FF4D6D", fontSize: 15, fontWeight: "700" },
  bpCalibratePromptText: { color: "#aaa", fontSize: 13, lineHeight: 18 },
});
