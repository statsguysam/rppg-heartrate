import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";

interface ErrorBannerProps {
  message: string;
  onRetry: () => void;
}

export default function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.icon}>⚠</Text>
      <Text style={styles.message} numberOfLines={3}>
        {message}
      </Text>
      <TouchableOpacity style={styles.retryButton} onPress={onRetry}>
        <Text style={styles.retryText}>Try Again</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    margin: 16,
    padding: 16,
    backgroundColor: "#2a0a0a",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#F87171",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: 8,
  },
  icon: {
    fontSize: 20,
    color: "#F87171",
  },
  message: {
    color: "#fca5a5",
    fontSize: 14,
    lineHeight: 20,
  },
  retryButton: {
    alignSelf: "flex-end",
    backgroundColor: "#F87171",
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 14,
  },
});
