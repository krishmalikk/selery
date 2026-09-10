import { useCallback, useRef, useState } from "react";
import { AppState, Text } from "react-native";
import { useFocusEffect } from "expo-router";
import type { PublicActivity } from "@selery/shared";
import { ExternalLink, styles } from "./ui";

export const sourceNames = { etoro: "eToro", kinfo: "Kinfo", afterhour: "AfterHour" };
export const activityStatus = {
  observed_open: "Observed open",
  no_longer_observed: "No longer observed · exit unconfirmed",
  access_unavailable: "Access unavailable",
};
export const instrumentNames = {
  stock: "Stock", stock_cfd: "Stock CFD", other: "Other instrument", unclassified: "Unclassified instrument",
};
export function publicTime(value: string | null) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleString();
}
export function publicNumber(value: number | null) {
  return value === null ? "Unavailable" : value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}
export function PublicSourceLink({ source, url, label }: { source: PublicActivity["source"]; url: string; label: string }) {
  let safe = false;
  try {
    const parsed = new URL(url);
    const domain = { etoro: "etoro.com", kinfo: "kinfo.com", afterhour: "afterhour.com" }[source];
    safe = parsed.protocol === "https:" && !parsed.username && !parsed.password && !parsed.port
      && (parsed.hostname === domain || parsed.hostname.endsWith(`.${domain}`));
  } catch {}
  return safe ? <ExternalLink url={url} label={label} /> : <Text style={styles.muted}>Source link unavailable</Text>;
}

// Public access can be withdrawn: keep records in screen memory only, clear on
// blur/background, and always fetch again before displaying a focused screen.
export function usePublicResource<T>(fetcher: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  const active = useRef(false);
  const refresh = useCallback(async () => {
    if (!active.current) return;
    const request = ++generation.current;
    setData(null);
    setError("");
    setLoading(true);
    try {
      const result = await fetcher();
      if (active.current && request === generation.current) setData(result);
    } catch (e) {
      if (active.current && request === generation.current)
        setError(e instanceof Error ? e.message : "Unable to retrieve public research records");
    } finally {
      if (active.current && request === generation.current) setLoading(false);
    }
  }, [fetcher]);
  useFocusEffect(useCallback(() => {
    active.current = true;
    void refresh();
    const clear = () => {
      active.current = false;
      generation.current++;
      setData(null);
    };
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") { active.current = true; void refresh(); }
      else clear();
    });
    return () => { clear(); subscription.remove(); };
  }, [refresh]));
  return { data, error, loading, refresh };
}
export function PublicStatus({ loading, error }: { loading: boolean; error: string }) {
  return <>
    {loading && <Text style={styles.muted}>Retrieving public research records…</Text>}
    {!!error && <Text accessibilityRole="alert" style={styles.warning}>{error}. Public records are unavailable offline; reconnect and retry.</Text>}
  </>;
}
