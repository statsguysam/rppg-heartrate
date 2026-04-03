import React from "react";
import { ScrollView, Text, StyleSheet, SafeAreaView } from "react-native";

export default function PrivacyScreen() {
  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Privacy Policy</Text>
        <Text style={styles.date}>Last updated: April 2026</Text>

        <Text style={styles.section}>What we collect</Text>
        <Text style={styles.body}>
          Heart Rate Monitor records a short video of your face to estimate your
          heart rate using remote photoplethysmography (rPPG). The video is sent
          to our processing server over an encrypted connection (HTTPS), analyzed,
          and immediately deleted. We do not store your video, facial data, or any
          biometric identifiers.
        </Text>

        <Text style={styles.section}>Heart rate readings</Text>
        <Text style={styles.body}>
          Estimated BPM readings are stored locally on your device only
          (AsyncStorage). They are never uploaded, shared, or sold. You can
          delete all readings at any time from the History tab.
        </Text>

        <Text style={styles.section}>Camera & microphone</Text>
        <Text style={styles.body}>
          Camera permission is required to record the face video. Microphone
          permission is required by the operating system for video recording;
          audio is not processed, transmitted, or stored.
        </Text>

        <Text style={styles.section}>No third-party analytics</Text>
        <Text style={styles.body}>
          This app contains no advertising SDKs, no tracking pixels, and no
          analytics libraries. It does not share any data with third parties.
        </Text>

        <Text style={styles.section}>Medical disclaimer</Text>
        <Text style={styles.body}>
          This app is not a medical device and is not intended to diagnose,
          treat, cure, or prevent any disease or health condition. Always consult
          a qualified healthcare professional for medical advice.
        </Text>

        <Text style={styles.section}>Contact</Text>
        <Text style={styles.body}>
          Developer: Salim Shaikh{"\n"}
          Email: statsguysalim@gmail.com{"\n"}
          Support: https://salimshaikh.github.io/rppg-heartrate
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#0a0a0a" },
  container: { padding: 24, gap: 12 },
  title: { color: "#fff", fontSize: 24, fontWeight: "800", marginBottom: 4 },
  date: { color: "#666", fontSize: 13, marginBottom: 8 },
  section: { color: "#FF4D6D", fontSize: 15, fontWeight: "700", marginTop: 12 },
  body: { color: "#aaa", fontSize: 14, lineHeight: 22 },
});
