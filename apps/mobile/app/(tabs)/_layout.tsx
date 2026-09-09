import React, { useEffect } from "react";
import { Tabs, useRouter } from "expo-router";
import { subscribeNotificationLinks } from "../../src/notifications";
import { Text } from "react-native";
import { c } from "../../src/ui";
const screens = [
  ["index", "Watchlist", "◈"],
  ["chart", "Chart", "⌁"],
  ["news", "News", "≡"],
  ["alerts", "Alerts", "◇"],
  ["journal", "Journal", "▤"],
  ["settings", "Settings", "⚙"],
] as const;
export default function TabLayout() {
  const router = useRouter();
  useEffect(() => {
    let cleanup: (() => void) | undefined;
    let closed = false;
    subscribeNotificationLinks((symbol, signal) =>
      router.navigate({
        pathname: "/chart",
        params: { symbol, ...(signal ? { signal } : {}) },
      }),
    )
      .then((fn) => {
        if (closed) fn();
        else cleanup = fn;
      })
      .catch(() => {});
    return () => {
      closed = true;
      cleanup?.();
    };
  }, [router]);
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: c.accent,
        tabBarInactiveTintColor: c.muted,
        tabBarStyle: { backgroundColor: c.surface, borderTopColor: c.border },
        tabBarLabelStyle: { fontSize: 10 },
      }}
    >
      {screens.map(([name, title, icon]) => (
        <Tabs.Screen
          key={name}
          name={name}
          options={{
            title,
            tabBarIcon: ({ color }) => (
              <Text style={{ color, fontSize: 22 }}>{icon}</Text>
            ),
          }}
        />
      ))}
    </Tabs>
  );
}
