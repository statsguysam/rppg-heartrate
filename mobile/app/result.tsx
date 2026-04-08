import React, { useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
} from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { saveScan } from "../services/api";

import HeartRateDisplay from "../components/HeartRateDisplay";
import WaveformChart from "../components/WaveformChart";

export default function ResultScreen() {
  const { bpm, confidence, waveform, waveform_fps, age, sex, activity, stress, caffeine, medications } = useLocalSearchParams<{
    bpm: string; confidence: string; waveform: string; waveform_fps: string;
    age: string; sex: string; activity: string; stress: string; caffeine: string; medications: string;
  }>();

  const bpmVal = parseFloat(bpm ?? "0");
  const confVal = parseFloat(confidence ?? "0");
  const waveformData: number[] = waveform ? JSON.parse(waveform) : [];

  // Save reading to history
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
      } catch {
        // Storage error is non-fatal
      }
    };
    save();

    // Save to remote database (non-fatal if fails)
    saveScan({
      bpm: bpmVal,
      confidence: confVal,
      age: age ? parseInt(age) : undefined,
      sex: sex || undefined,
      activity: activity || undefined,
      stress: stress || undefined,
      caffeine: caffeine || undefined,
      medications: medications || undefined,
    });
  }, []);

  const bpmCategory = bpmVal < 60 ? "Bradycardia" : bpmVal > 100 ? "Tachycardia" : "Normal";
  const bpmCategoryColor = bpmVal < 60 || bpmVal > 100 ? "#FACC15" : "#4ADE80";

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
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

        {/* CTA */}
        <TouchableOpacity
          style={styles.measureAgainButton}
          onPress={() => router.replace("/")}
        >
          <Text style={styles.measureAgainText}>Measure Again</Text>
        </TouchableOpacity>
      </ScrollView>
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
  measureAgainText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 16,
  },
});
