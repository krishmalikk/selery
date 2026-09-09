import type { NotificationResponse } from "expo-notifications";
import Constants from "expo-constants";
import * as Device from "expo-device";
import { Platform } from "react-native";
// Dynamic import keeps remote-notification initialization out of Expo Go.
export async function registerNotifications(): Promise<string> {
  if (Constants.appOwnership === "expo")
    throw new Error(
      "Push requires an EAS development build; Expo Go supports browsing the app.",
    );
  if (!Device.isDevice)
    throw new Error("Push registration requires a physical device.");
  const projectId = Constants.expoConfig?.extra?.eas?.projectId;
  if (!projectId)
    throw new Error(
      "Configure EXPO_PUBLIC_EAS_PROJECT_ID and signing credentials first.",
    );
  const Notifications = await import("expo-notifications");
  if (Platform.OS === "android")
    await Notifications.setNotificationChannelAsync("research", {
      name: "Research updates",
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  let permission = await Notifications.getPermissionsAsync();
  if (permission.status !== "granted")
    permission = await Notifications.requestPermissionsAsync();
  if (permission.status !== "granted")
    throw new Error("Notification permission was not granted.");
  return (await Notifications.getExpoPushTokenAsync({ projectId })).data;
}
export async function subscribeNotificationLinks(
  open: (symbol: string, signal?: string) => void,
) {
  if (Constants.appOwnership === "expo") return () => {};
  const Notifications = await import("expo-notifications");
  const receive = (response: NotificationResponse) => {
    const data = response.notification.request.content.data ?? {};
    const symbol = typeof data.symbol === "string" ? data.symbol : "";
    if (/^[A-Z.]{1,10}$/.test(symbol))
      open(
        symbol,
        typeof data.signal_id === "string" ? data.signal_id : undefined,
      );
  };
  const last = await Notifications.getLastNotificationResponseAsync();
  if (last) receive(last);
  const subscription =
    Notifications.addNotificationResponseReceivedListener(receive);
  return () => subscription.remove();
}
