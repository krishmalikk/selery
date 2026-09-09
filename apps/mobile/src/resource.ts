import { useCallback, useEffect, useRef, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import type { z } from "zod";
import { useSession } from "./session";
export function useResource<T>(
  key: string,
  fetcher: () => Promise<T>,
  schema: z.ZodType<T>,
) {
  const { authenticated, endpoint } = useSession();
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [cached, setCached] = useState(false),
    [updated, setUpdated] = useState<number | null>(null);
  const storageKey = `selery:${endpoint}:${key}`;
  const current = useRef(storageKey);
  current.current = storageKey;
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  // Ignore late responses when a chart key changes or the session unmounts.
  const refresh = useCallback(async () => {
    if (!authenticated) return;
    const valid = () => mounted.current && current.current === storageKey;
    setLoading(true);
    try {
      const result = await fetcher();
      if (!valid()) return;
      const at = Date.now();
      setData(result);
      setCached(false);
      setUpdated(at);
      setError("");
      await AsyncStorage.setItem(
        storageKey,
        JSON.stringify({ data: result, at }),
      );
    } catch (e) {
      if (valid()) {
        setError(e instanceof Error ? e.message : "Unable to refresh");
        setCached(true);
      }
    } finally {
      if (valid()) setLoading(false);
    }
  }, [authenticated, fetcher, storageKey]);
  useEffect(() => {
    let active = true;
    setData(null);
    setUpdated(null);
    setLoading(true);
    AsyncStorage.getItem(storageKey)
      .then((raw) => {
        if (raw && active) {
          try {
            const value = JSON.parse(raw);
            setData(schema.parse(value.data));
            setUpdated(value.at);
            setCached(true);
          } catch {}
        }
      })
      .catch(() => {})
      .finally(() => {
        if (active) void refresh();
      });
    return () => {
      active = false;
    };
  }, [refresh, schema, storageKey]);
  return { data, error, loading, cached, updated, refresh };
}
