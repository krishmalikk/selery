import React from "react";
import {
  StyleSheet,
  Text,
  View,
  Pressable,
  ScrollView,
  RefreshControl,
  TextInput,
  type TextInputProps,
} from "react-native";
import {
  tokens,
  disclaimer,
  feedLabel,
  type Feed,
  formatTime,
} from "@selery/shared";
export const c = tokens.color;
export const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: c.background },
  content: { padding: 20, paddingBottom: 32, gap: 16 },
  title: {
    fontSize: 28,
    fontWeight: "600",
    color: c.text,
    letterSpacing: -0.8,
  },
  heading: { fontSize: 18, fontWeight: "600", color: c.text },
  text: {
    fontFamily: tokens.font.sans,
    color: c.text,
    fontSize: 15,
    lineHeight: 23,
  },
  muted: { color: c.muted, fontSize: 12, lineHeight: 18 },
  mono: { fontFamily: tokens.font.mono, color: c.text, fontSize: 22 },
  card: {
    backgroundColor: c.surface,
    borderColor: c.border,
    borderWidth: 1,
    borderRadius: 16,
    padding: 18,
    gap: 9,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
  },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  button: {
    backgroundColor: c.accent,
    paddingHorizontal: 18,
    paddingVertical: 13,
    borderRadius: 12,
    alignItems: "center",
  },
  buttonText: { color: c.background, fontWeight: "700" },
  input: {
    borderWidth: 1,
    borderColor: c.border,
    borderRadius: 12,
    padding: 14,
    color: c.text,
    backgroundColor: c.surface,
    fontSize: 16,
    minHeight: 48,
  },
  warning: { color: c.warning, fontSize: 12, lineHeight: 18 },
  badge: {
    color: c.warning,
    fontSize: 11,
    borderColor: c.border,
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 7,
    paddingVertical: 3,
  },
  footer: {
    color: c.muted,
    fontSize: 10,
    lineHeight: 14,
    paddingHorizontal: 16,
    paddingVertical: 7,
    borderTopColor: c.border,
    borderTopWidth: 1,
    backgroundColor: c.background,
  },
});
export function Page({
  title,
  children,
  refresh,
  loading = false,
}: {
  title: string;
  children: React.ReactNode;
  refresh?: () => void;
  loading?: boolean;
}) {
  return (
    <ScrollView
      style={styles.page}
      contentContainerStyle={styles.content}
      refreshControl={
        refresh ? (
          <RefreshControl
            tintColor={c.accent}
            refreshing={loading}
            onRefresh={refresh}
          />
        ) : undefined
      }
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.title}>{title}</Text>
      {children}
    </ScrollView>
  );
}
export function Card({ children }: { children: React.ReactNode }) {
  return <View style={styles.card}>{children}</View>;
}
export function Button({
  title,
  onPress,
  disabled = false,
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      onPress={onPress}
      disabled={disabled}
      style={[styles.button, disabled && { opacity: 0.45 }]}
    >
      <Text style={styles.buttonText}>{title}</Text>
    </Pressable>
  );
}
export function Input(props: TextInputProps) {
  return (
    <TextInput
      placeholderTextColor={c.muted}
      {...props}
      style={[
        styles.input,
        props.multiline && { minHeight: 100, textAlignVertical: "top" },
        props.style,
      ]}
    />
  );
}
export function FeedBadge({ feed }: { feed: Feed }) {
  return <Text style={styles.badge}>{feedLabel(feed)}</Text>;
}
export function ResourceStatus({
  error,
  cached,
  updated,
  loading,
}: {
  error: string;
  cached: boolean;
  updated: number | null;
  loading: boolean;
}) {
  return (
    <View>
      {loading && <Text style={styles.muted}>Refreshing…</Text>}
      {cached && (
        <Text style={styles.warning}>
          Offline / last-known data. Values may be stale.
        </Text>
      )}
      {updated && (
        <Text style={styles.muted}>Retrieved {formatTime(updated / 1000)}</Text>
      )}
      {!!error && (
        <Text accessibilityRole="alert" style={styles.warning}>
          {error}
        </Text>
      )}
    </View>
  );
}
export function Disclaimer() {
  return <Text style={styles.footer}>{disclaimer}</Text>;
}
export function ExternalLink({ url, label }: { url: string; label: string }) {
  const { Linking } = require("react-native");
  return (
    <Pressable
      accessibilityRole="link"
      onPress={() => {
        if (/^https?:\/\//.test(url)) void Linking.openURL(url);
      }}
    >
      <Text style={{ color: c.accent, fontSize: 14 }}>{label} ↗</Text>
    </Pressable>
  );
}
