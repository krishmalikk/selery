import type { ExpoConfig } from "expo/config";
const config: ExpoConfig = {
  name: "Selery",
  slug: "selery",
  scheme: "selery",
  version: "0.1.0",
  orientation: "default",
  userInterfaceStyle: "dark",
  ios: {
    supportsTablet: true,
    bundleIdentifier: process.env.SELERY_IOS_BUNDLE_ID || "com.selery.research",
    infoPlist: {
      NSAppTransportSecurity: { NSAllowsLocalNetworking: true },
      ITSAppUsesNonExemptEncryption: false,
    },
  },
  android: {
    package: process.env.SELERY_ANDROID_PACKAGE || "com.selery.research",
  },
  plugins: ["expo-router", "expo-secure-store", "expo-notifications"],
  extra: {
    eas: { projectId: process.env.EXPO_PUBLIC_EAS_PROJECT_ID || undefined },
  },
};
export default config;
