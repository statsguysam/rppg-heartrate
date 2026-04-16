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

import HeartRateDisplay from "../components/HeartRateDisplay";
import WaveformChart from "../components/WaveformChart";

export default function ResultScreen() {
  const {
    bpm, confidence, waveform, waveform_fps,
    age, sex, activity, stress, caffeine, medications, video_url,
    sbp, dbp, bp_confidence,
    rmssd_ms, sdnn_ms, pnn50, hrv_confidence,
    respiration_bpm, respiration_confidence,
    stress_score, stress_label, stress_lf_hf, stress_confidence,
  } = useLocalSearchParams<{
    bpm: string; confidence: string; waveform: string; waveform_fps: string;
    age: string; sex: string; activity: string; stress: string; caffeine: string; medications: string; video_url: string;
    sbp?: string; dbp?: string; bp_confidence?: string;
    rmssd_ms?: string; sdnn_ms?: string; pnn50?: string; hrv_confidence?: string;
    respiration_bpm?: string; respiration_confidence?: string;
    stress_score?: string; stress_label?: string; stress_lf_hf?: string; stress_confidence?: string;
  }>();

  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const bpmVal = parseFloat(bpm ?? "0");
  const confVal = parseFloat(confidence ?? "0");
  const waveformData: number[] = waveform ? JSON.parse(waveform) : [];

  const sbpVal = sbp ? parseFloat(sbp) : null;
  const dbpVal = dbp ? parseFloat(dbp) : null;
  const bpConf = bp_confidence ? parseFloat(bp_confidence) : null;

  const rmssdVal = rmssd_ms ? parseFloat(rmssd_ms) : null;
  const sdnnVal = sdnn_ms ? parseFloat(sdnn_ms) : null;
  const pnn50Val = pnn50 ? parseFloat(pnn50) : null;
  const hrvConf = hrv_confidence ? parseFloat(hrv_confidence) : null;

  const respVal = respiration_bpm ? parseFloat(respiration_bpm) : null;
  const respConf = respiration_confidence ? parseFloat(respiration_confidence) : null;

  const stressVal = stress_score ? parseInt(stress_score, 10) : null;
  const stressLabel = stress_label || null;
  const lfHfVal = stress_lf_hf ? parseFloat(stress_lf_hf) : null;
  const stressConf = stress_confidence ? parseFloat(stress_confidence) : null;

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
          sbp: sbpVal,
          dbp: dbpVal,
          bp_confidence: bpConf,
          rmssd_ms: rmssdVal,
          sdnn_ms: sdnnVal,
          pnn50: pnn50Val,
          respiration_bpm: respVal,
          stress_score: stressVal,
          stress_label: stressLabel,
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

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await saveScan({
        bpm: bpmVal,
        confidence: confVal,
        sbp: sbpVal ?? undefined,
        dbp: dbpVal ?? undefined,
        bp_confidence: bpConf ?? undefined,
        rmssd_ms: rmssdVal ?? undefined,
        sdnn_ms: sdnnVal ?? undefined,
        pnn50: pnn50Val ?? undefined,
        hrv_confidence: hrvConf ?? undefined,
        respiration_bpm: respVal ?? undefined,
        respiration_confidence: respConf ?? undefined,
        stress_score: stressVal ?? undefined,
        stress_label: stressLabel ?? undefined,
        stress_lf_hf: lfHfVal ?? undefined,
        stress_confidence: stressConf ?? undefined,
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

  const bpCategory = (() => {
    if (sbpVal == null || dbpVal == null) return null;
    if (sbpVal < 90 || dbpVal < 60) return { label: "Low", color: "#FACC15" };
    if (sbpVal >= 140 || dbpVal >= 90) return { label: "High (Stage 2)", color: "#FB7185" };
    if (sbpVal >= 130 || dbpVal >= 80) return { label: "High (Stage 1)", color: "#FACC15" };
    if (sbpVal >= 120) return { label: "Elevated", color: "#FACC15" };
    return { label: "Normal", color: "#4ADE80" };
  })();

  const respCategory = (() => {
    if (respVal == null) return null;
    if (respVal < 12) return { label: "Low", color: "#FACC15" };
    if (respVal > 20) return { label: "Elevated", color: "#FACC15" };
    return { label: "Normal", color: "#4ADE80" };
  })();

  const stressColor = (() => {
    if (stressLabel === "Low") return "#4ADE80";
    if (stressLabel === "Normal") return "#4ADE80";
    if (stressLabel === "Elevated") return "#FACC15";
    if (stressLabel === "High") return "#FB7185";
    return "#888";
  })();

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

        {/* Blood pressure */}
        {sbpVal != null && dbpVal != null && (
          <View style={styles.bpCard}>
            <Text style={styles.cardTitle}>Blood Pressure</Text>
            <View style={styles.bpRow}>
              <Text style={styles.bpNumber}>{Math.round(sbpVal)}</Text>
              <Text style={styles.bpSlash}>/</Text>
              <Text style={styles.bpNumber}>{Math.round(dbpVal)}</Text>
              <Text style={styles.bpUnit}>mmHg</Text>
            </View>
            {bpCategory && (
              <View style={[styles.bpBadge, { borderColor: bpCategory.color }]}>
                <Text style={[styles.bpBadgeText, { color: bpCategory.color }]}>{bpCategory.label}</Text>
              </View>
            )}
            {bpConf != null && (
              <Text style={styles.bpSubtle}>
                Signal confidence {Math.round(bpConf * 100)}% · wellness estimate, not a medical measurement
              </Text>
            )}
          </View>
        )}

        {/* Respiration */}
        {respVal != null && (
          <View style={styles.metricCard}>
            <Text style={styles.cardTitle}>Respiration Rate</Text>
            <View style={styles.metricRow}>
              <Text style={styles.metricNumber}>{Math.round(respVal)}</Text>
              <Text style={styles.metricUnit}>breaths/min</Text>
            </View>
            {respCategory && (
              <View style={[styles.bpBadge, { borderColor: respCategory.color }]}>
                <Text style={[styles.bpBadgeText, { color: respCategory.color }]}>{respCategory.label}</Text>
              </View>
            )}
            {respConf != null && (
              <Text style={styles.bpSubtle}>
                Signal confidence {Math.round(respConf * 100)}% · Normal adult range 12–20
              </Text>
            )}
          </View>
        )}

        {/* Stress */}
        {stressVal != null && stressLabel && (
          <View style={styles.metricCard}>
            <Text style={styles.cardTitle}>Stress Level</Text>
            <View style={styles.metricRow}>
              <Text style={[styles.metricNumber, { color: stressColor }]}>{stressVal}</Text>
              <Text style={styles.metricUnit}>/ 100</Text>
            </View>
            <View style={[styles.bpBadge, { borderColor: stressColor }]}>
              <Text style={[styles.bpBadgeText, { color: stressColor }]}>{stressLabel}</Text>
            </View>
            <View style={styles.hrvRow}>
              {lfHfVal != null && (
                <View style={styles.hrvItem}>
                  <Text style={styles.hrvKey}>LF/HF</Text>
                  <Text style={styles.hrvVal}>{lfHfVal.toFixed(2)}</Text>
                </View>
              )}
            </View>
            {stressConf != null && (
              <Text style={styles.bpSubtle}>
                Baevsky SI + LF/HF blend · confidence {Math.round(stressConf * 100)}%
              </Text>
            )}
          </View>
        )}

        {/* HRV */}
        {(rmssdVal != null || sdnnVal != null) && (
          <View style={styles.metricCard}>
            <Text style={styles.cardTitle}>Heart Rate Variability</Text>
            <View style={styles.hrvRow}>
              {rmssdVal != null && (
                <View style={styles.hrvItem}>
                  <Text style={styles.hrvKey}>RMSSD</Text>
                  <Text style={styles.hrvVal}>{Math.round(rmssdVal)} ms</Text>
                </View>
              )}
              {sdnnVal != null && (
                <View style={styles.hrvItem}>
                  <Text style={styles.hrvKey}>SDNN</Text>
                  <Text style={styles.hrvVal}>{Math.round(sdnnVal)} ms</Text>
                </View>
              )}
              {pnn50Val != null && (
                <View style={styles.hrvItem}>
                  <Text style={styles.hrvKey}>pNN50</Text>
                  <Text style={styles.hrvVal}>{Math.round(pnn50Val * 100)}%</Text>
                </View>
              )}
            </View>
            {hrvConf != null && (
              <Text style={styles.bpSubtle}>
                Signal confidence {Math.round(hrvConf * 100)}% · Higher RMSSD usually reflects better recovery
              </Text>
            )}
          </View>
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
  bpBadge: {
    borderWidth: 1, borderRadius: 16,
    paddingHorizontal: 12, paddingVertical: 4, marginTop: 4,
  },
  bpBadgeText: { fontSize: 12, fontWeight: "700", letterSpacing: 0.5 },
  bpSubtle: { color: "#666", fontSize: 12, textAlign: "center", paddingHorizontal: 8 },
  metricCard: {
    width: "100%", backgroundColor: "#141414", borderRadius: 16,
    padding: 20, gap: 8, alignItems: "center",
  },
  metricRow: { flexDirection: "row", alignItems: "baseline", gap: 8 },
  metricNumber: { color: "#FF4D6D", fontSize: 40, fontWeight: "800", lineHeight: 44 },
  metricUnit: { color: "#FF4D6D99", fontSize: 13, fontWeight: "600", letterSpacing: 1 },
  hrvRow: { flexDirection: "row", flexWrap: "wrap", gap: 12, justifyContent: "center", marginTop: 4 },
  hrvItem: { alignItems: "center", minWidth: 72 },
  hrvKey: { color: "#888", fontSize: 11, fontWeight: "600", letterSpacing: 0.5 },
  hrvVal: { color: "#fff", fontSize: 16, fontWeight: "700", marginTop: 2 },
});
