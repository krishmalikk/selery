import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import * as SecureStore from "expo-secure-store";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { SeleryClient } from "@selery/shared";
const endpoint = (
  process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/$/, "");
const tokenKey = "selery.session";
type Session = {
  client: SeleryClient;
  ready: boolean;
  authenticated: boolean;
  login: (password: string) => Promise<void>;
  logout: () => Promise<void>;
  endpoint: string;
};
const Context = createContext<Session>(null!);
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null),
    [ready, setReady] = useState(false),
    [expiresAt, setExpiresAt] = useState<number | null>(null);
  useEffect(() => {
    SecureStore.getItemAsync(tokenKey)
      .then((saved) => {
        if (saved) {
          try {
            const value = JSON.parse(saved);
            if (value.expiresAt > Date.now()) {
              setToken(value.token);
              setExpiresAt(value.expiresAt);
            }
          } catch {}
        }
      })
      .catch(() => setToken(null))
      .finally(() => setReady(true));
  }, []);
  useEffect(() => {
    if (!expiresAt) return;
    const timer = setTimeout(
      () => {
        setToken(null);
        setExpiresAt(null);
        void SecureStore.deleteItemAsync(tokenKey);
      },
      Math.max(0, expiresAt - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [expiresAt]);
  const client = useMemo(
    () => new SeleryClient(endpoint, () => token),
    [token],
  );
  async function login(password: string) {
    const result = await client.login(password);
    await SecureStore.setItemAsync(
      tokenKey,
      JSON.stringify({
        token: result.token,
        expiresAt: Date.now() + result.expires_in * 1000,
      }),
    );
    setToken(result.token);
    setExpiresAt(Date.now() + result.expires_in * 1000);
  }
  async function logout() {
    try {
      await client.logout();
    } finally {
      await SecureStore.deleteItemAsync(tokenKey);
      const keys = (await AsyncStorage.getAllKeys()).filter((key) =>
        key.startsWith("selery:"),
      );
      await AsyncStorage.multiRemove(keys);
      setToken(null);
      setExpiresAt(null);
    }
  }
  return (
    <Context.Provider
      value={{ client, ready, authenticated: !!token, login, logout, endpoint }}
    >
      {children}
    </Context.Provider>
  );
}
export const useSession = () => useContext(Context);
