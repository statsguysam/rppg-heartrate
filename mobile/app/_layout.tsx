import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

export default function RootLayout() {
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
        <Stack.Screen
          name="calibrate"
          options={{
            title: "BP Calibration",
            headerBackTitle: "Back",
            presentation: "card",
          }}
        />
      </Stack>
    </>
  );
}
