import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  Alert,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useFocusEffect } from "expo-router";

interface Reading {
  id: string;
  bpm: number;
  confidence: number;
  timestamp: string;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function bpmColor(bpm: number): string {
  if (bpm < 60 || bpm > 100) return "#FACC15";
  return "#4ADE80";
}

export default function HistoryScreen() {
  const [history, setHistory] = useState<Reading[]>([]);

  const loadHistory = useCallback(async () => {
    const stored = await AsyncStorage.getItem("hr_history");
    setHistory(stored ? JSON.parse(stored) : []);
  }, []);

  useFocusEffect(loadHistory);

  const clearHistory = () => {
    Alert.alert("Clear History", "Delete all readings?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete All",
        style: "destructive",
        onPress: async () => {
          await AsyncStorage.removeItem("hr_history");
          setHistory([]);
        },
      },
    ]);
  };

  if (history.length === 0) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.emptyState}>
          <Text style={styles.emptyIcon}>♡</Text>
          <Text style={styles.emptyTitle}>No readings yet</Text>
          <Text style={styles.emptySubtitle}>
            Your heart rate readings will appear here after you record a scan.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <FlatList
        data={history}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        ListHeaderComponent={
          <TouchableOpacity style={styles.clearButton} onPress={clearHistory}>
            <Text style={styles.clearButtonText}>Clear All</Text>
          </TouchableOpacity>
        }
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.cardLeft}>
              <Text style={[styles.bpmText, { color: bpmColor(item.bpm) }]}>
                {item.bpm.toFixed(0)}
              </Text>
              <Text style={styles.bpmUnit}>BPM</Text>
            </View>
            <View style={styles.cardRight}>
              <Text style={styles.dateText}>{formatDate(item.timestamp)}</Text>
              <Text style={styles.confidenceText}>
                Confidence: {Math.round(item.confidence * 100)}%
              </Text>
            </View>
          </View>
        )}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#0a0a0a",
  },
  emptyState: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
    gap: 12,
  },
  emptyIcon: {
    fontSize: 48,
    color: "#FF4D6D",
  },
  emptyTitle: {
    color: "#fff",
    fontSize: 20,
    fontWeight: "700",
  },
  emptySubtitle: {
    color: "#666",
    fontSize: 14,
    textAlign: "center",
    lineHeight: 20,
  },
  listContent: {
    padding: 16,
    gap: 2,
  },
  clearButton: {
    alignSelf: "flex-end",
    marginBottom: 12,
  },
  clearButtonText: {
    color: "#F87171",
    fontSize: 14,
    fontWeight: "600",
  },
  card: {
    flexDirection: "row",
    backgroundColor: "#141414",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    gap: 16,
  },
  cardLeft: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 4,
    minWidth: 80,
  },
  bpmText: {
    fontSize: 32,
    fontWeight: "800",
  },
  bpmUnit: {
    fontSize: 13,
    color: "#666",
    fontWeight: "600",
  },
  cardRight: {
    flex: 1,
    gap: 4,
  },
  dateText: {
    color: "#ccc",
    fontSize: 14,
    fontWeight: "500",
  },
  confidenceText: {
    color: "#666",
    fontSize: 13,
  },
  separator: {
    height: 8,
  },
});
