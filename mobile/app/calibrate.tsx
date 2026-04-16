import React, { useEffect, useState } from "react";
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
  Alert,
} from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { loadCalibration, clearCalibration } from "../services/calibration";

/**
 * One-time BP calibration flow:
 *   1. User enters a fresh cuff BP reading.
 *   2. We route them to a 60 s face scan (same /scan screen).
 *   3. After the scan, the /result screen pairs the cuff reading with the
 *      model's raw prediction and stores the offset on-device.
 *
 * Without calibration we hide BP entirely; showing an uncalibrated number
 * would give users ±15 mmHg noise as if it were a measurement.
 */
export default function CalibrateScreen() {
  const { return_to } = useLocalSearchParams<{ return_to?: string }>();
  const [sbp, setSbp] = useState("");
  const [dbp, setDbp] = useState("");
  const [existing, setExisting] = useState<boolean>(false);

  useEffect(() => {
    loadCalibration().then((cal) => setExisting(!!cal));
  }, []);

  const sbpN = parseInt(sbp, 10);
  const dbpN = parseInt(dbp, 10);
  const valid =
    sbp.length > 0 && dbp.length > 0 &&
    sbpN >= 80 && sbpN <= 220 &&
    dbpN >= 40 && dbpN <= 140 &&
    sbpN > dbpN + 15;

  const handleProceed = () => {
    if (!valid) return;
    // Hand cuff values to /scan → /result will pair them with the model output.
    router.push({
      pathname: "/scan",
      params: {
        calibration: "1",
        cuff_sbp: String(sbpN),
        cuff_dbp: String(dbpN),
        return_to: return_to ?? "/",
      },
    });
  };

  const handleReset = () =>
    Alert.alert("Clear calibration?", "You'll be prompted again on your next scan.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Clear",
        style: "destructive",
        onPress: async () => {
          await clearCalibration();
          setExisting(false);
        },
      },
    ]);

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : "height"}>
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <Text style={styles.title}>Calibrate Blood Pressure</Text>
            <Text style={styles.subtitle}>
              One-time setup. Take a reading with a cuff monitor, enter the numbers below,
              then do a 60-second face scan. Future scans will be calibrated to you.
            </Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Recent cuff BP reading</Text>
            <Text style={styles.hint}>Use a reading from the last few hours if possible.</Text>

            <View style={styles.inputRow}>
              <View style={styles.inputGroup}>
                <Text style={styles.label}>Systolic (top)</Text>
                <TextInput
                  style={styles.input}
                  placeholder="120"
                  placeholderTextColor="#555"
                  keyboardType="number-pad"
                  value={sbp}
                  onChangeText={setSbp}
                  maxLength={3}
                />
              </View>
              <Text style={styles.slash}>/</Text>
              <View style={styles.inputGroup}>
                <Text style={styles.label}>Diastolic (bottom)</Text>
                <TextInput
                  style={styles.input}
                  placeholder="80"
                  placeholderTextColor="#555"
                  keyboardType="number-pad"
                  value={dbp}
                  onChangeText={setDbp}
                  maxLength={3}
                />
              </View>
              <Text style={styles.unit}>mmHg</Text>
            </View>

            {!valid && sbp.length > 0 && dbp.length > 0 && (
              <Text style={styles.validation}>
                Enter a plausible reading (SBP 80–220, DBP 40–140, SBP &gt; DBP+15).
              </Text>
            )}
          </View>

          <View style={styles.infoCard}>
            <Text style={styles.infoTitle}>Why calibrate?</Text>
            <Text style={styles.infoText}>
              rPPG models predict the population average. A per-person offset
              typically cuts BP error from ~15 mmHg to ~5 mmHg. Re-calibrate
              every two weeks for best accuracy.
            </Text>
          </View>

          <TouchableOpacity
            style={[styles.primaryButton, !valid && styles.primaryButtonDisabled]}
            onPress={handleProceed}
            disabled={!valid}
          >
            <Text style={styles.primaryButtonText}>Continue to Calibration Scan</Text>
          </TouchableOpacity>

          {existing && (
            <TouchableOpacity style={styles.secondaryButton} onPress={handleReset}>
              <Text style={styles.secondaryButtonText}>Clear existing calibration</Text>
            </TouchableOpacity>
          )}

          <Text style={styles.disclaimer}>
            Blood pressure estimates from video are a wellness signal, not a medical measurement.
            Consult a healthcare professional for diagnosis.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#0a0a0a" },
  container: { padding: 24, gap: 18, paddingBottom: 40 },
  header: { gap: 8, paddingTop: 8 },
  title: { color: "#fff", fontSize: 24, fontWeight: "800" },
  subtitle: { color: "#999", fontSize: 14, lineHeight: 20 },
  card: { backgroundColor: "#141414", borderRadius: 16, padding: 20, gap: 12 },
  cardTitle: { color: "#fff", fontSize: 16, fontWeight: "700" },
  hint: { color: "#666", fontSize: 13, marginTop: -6 },
  inputRow: { flexDirection: "row", alignItems: "flex-end", gap: 8 },
  inputGroup: { flex: 1, gap: 6 },
  label: { color: "#ccc", fontSize: 12, fontWeight: "600" },
  input: {
    backgroundColor: "#1e1e1e",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#2a2a2a",
    color: "#fff",
    fontSize: 20,
    fontWeight: "700",
    paddingHorizontal: 14,
    paddingVertical: 12,
    textAlign: "center",
  },
  slash: { color: "#555", fontSize: 28, fontWeight: "700", paddingBottom: 10 },
  unit: { color: "#666", fontSize: 12, paddingBottom: 16, marginLeft: 4 },
  validation: { color: "#F87171", fontSize: 12 },
  infoCard: { backgroundColor: "#0d1a14", borderRadius: 12, padding: 16, borderWidth: 1, borderColor: "#1a3a28", gap: 6 },
  infoTitle: { color: "#4ADE80", fontSize: 13, fontWeight: "700" },
  infoText: { color: "#aaa", fontSize: 13, lineHeight: 18 },
  primaryButton: {
    backgroundColor: "#FF4D6D", paddingVertical: 16,
    borderRadius: 30, alignItems: "center", marginTop: 8,
  },
  primaryButtonDisabled: { backgroundColor: "#FF4D6D44" },
  primaryButtonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  secondaryButton: { paddingVertical: 12, alignItems: "center" },
  secondaryButtonText: { color: "#888", fontSize: 14 },
  disclaimer: { color: "#444", fontSize: 12, textAlign: "center", lineHeight: 18, marginTop: 12 },
});
