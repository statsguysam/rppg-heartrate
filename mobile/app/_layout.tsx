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
          name="result"
          options={{
            title: "Your Results",
            headerBackTitle: "Record",
            presentation: "card",
          }}
        />
      </Stack>
    </>
  );
}
