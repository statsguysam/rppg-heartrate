import { useEffect } from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { warmupBackend } from "../services/api";

export default function RootLayout() {
  // Warm the Render worker on app launch. PhysMamba takes ~2 min per worker
  // to load on cold boot; if the first /analyze hits a cold worker it gets a
  // 502 from the proxy. A fire-and-forget /health ping gives the worker a
  // head-start so the model is ready by the time the user finishes scanning.
  useEffect(() => {
    warmupBackend();
  }, []);

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#0a0a0a" },
          headerTintColor: "#fff",
          contentStyle: { backgroundColor: "#0a0a0a" },
          animation: "slide_from_right",
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="scan"
          options={{ headerShown: false, presentation: "fullScreenModal" }}
        />
        <Stack.Screen
          name="result"
          options={{
            title: "Your Results",
            headerBackTitle: "Record",
            presentation: "card",
          }}
        />
        <Stack.Screen
          name="privacy"
          options={{
            title: "Privacy Policy",
            headerBackTitle: "Back",
            presentation: "card",
          }}
        />
      </Stack>
    </>
  );
}
