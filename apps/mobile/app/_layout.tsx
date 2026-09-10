import React, { useState } from "react";
import { Stack } from "expo-router";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { useFonts } from "expo-font";
import { Inter_400Regular } from "@expo-google-fonts/inter/400Regular";
import { JetBrainsMono_400Regular } from "@expo-google-fonts/jetbrains-mono/400Regular";
import { SessionProvider, useSession } from "../src/session";
import { Button, Input, styles, c, Disclaimer } from "../src/ui";
function Gate() {
  const { ready, authenticated, login, endpoint } = useSession();
  const [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  if (!ready)
    return (
      <View style={[styles.page, { justifyContent: "center", padding: 24 }]}>
        <Text style={styles.text}>Opening Selery…</Text>
      </View>
    );
  if (!authenticated)
    return (
      <SafeAreaView style={styles.page}>
        <View
          style={{ flex: 1, justifyContent: "center", padding: 28, gap: 20 }}
        >
          <Text style={[styles.title, { fontSize: 44 }]}>selery.</Text>
          <Text style={[styles.title, { fontSize: 32 }]}>Hi Krish.</Text>
          <Text style={styles.text}>
            Welcome back to your research workspace.
          </Text>
          <Input
            placeholder="Workspace password"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
            autoCapitalize="none"
            textContentType="password"
          />
          <Button
            title={busy ? "Signing in…" : "Open workspace"}
            disabled={busy || !password}
            onPress={() => {
              setBusy(true);
              setError("");
              login(password)
                .then(() => setPassword(""))
                .catch((e) => setError(e.message))
                .finally(() => setBusy(false));
            }}
          />
          {!!error && <Text style={styles.warning}>{error}</Text>}
          <Text style={styles.muted}>
            API: {endpoint}
            {"\n"}On a device, configure EXPO_PUBLIC_API_URL with your
            computer’s LAN address.
          </Text>
        </View>
        <Disclaimer />
      </SafeAreaView>
    );
  return (
    <SafeAreaView style={styles.page} edges={["top"]}>
      <View style={{ flex: 1 }}>
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: c.background },
          }}
        />
      </View>
      <Disclaimer />
    </SafeAreaView>
  );
}
export default function Layout() {
  useFonts({
    Inter: Inter_400Regular,
    "JetBrains Mono": JetBrainsMono_400Regular,
  });
  return (
    <SafeAreaProvider>
      <SessionProvider>
        <StatusBar style="light" />
        <Gate />
      </SessionProvider>
    </SafeAreaProvider>
  );
}
