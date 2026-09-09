# Mobile track

## Implemented

Expo SDK 57 / React Native 0.86.3 application with Expo Router native tabs: Watchlist, Chart, News, Alerts, Journal and Settings, plus a read-only research chat screen. Both platform exports include locally bundled Lightweight Charts 5.2.1 and local Inter/JetBrains Mono font assets. The renderer imports the same shared chart code used on desktop. TypeScript consumes generated schemas and the shared API client; all quantitative calculations remain server-side.

The app signs in with the workspace password and stores only an expiring session token in SecureStore. Provider credentials are never consumed by Expo. AsyncStorage retains validated last-known API responses and their retrieval timestamps; stale/offline data is labeled and sign-out clears the cache. Watchlist polling and ticket-authenticated WebSocket reconnect keep research data current when connected. Chart requests explicitly select IEX. Quote/volume values carry IEX labels; backend-disabled capabilities remain visible with their reason.

Native signal detail sheets show analytical reference/stop/target levels, provenance, horizon, and calibrated-confidence availability. Deep links use `selery://chart?symbol=SPY&signal=<id>`. The journal sends a mutation only from its explicit Save entry button. Chat provides source links and cost/mode disclosure. Remote notification registration is gated to physical devices with an EAS project ID in development/distribution builds. Notification taps navigate to the chart. Server token registration and delivery are not implemented; Settings explicitly says so and permits copying the token for an explicit test.

## Local start

From the repository root: `npm ci`, start the API on `0.0.0.0:8000`, then set `EXPO_PUBLIC_API_URL=http://YOUR_COMPUTER_LAN_IP:8000` and run `npm run mobile`. Open the QR code with an Expo Go version supporting SDK 57. A phone cannot reach the computer at `localhost`. API password comes from server configuration. `EXPO_PUBLIC_` variables are public and must never contain provider secrets. The chart build script runs before start/export; it requires no CDN or network at runtime.

## Distribution

`apps/mobile/eas.json` supplies development (development client), preview (internal iOS / Android APK), and production profiles. Configure `EXPO_PUBLIC_EAS_PROJECT_ID`, `SELERY_IOS_BUNDLE_ID`, `SELERY_ANDROID_PACKAGE`, a production HTTPS `EXPO_PUBLIC_API_URL`, and Expo project ownership before building. In `apps/mobile`, run `eas build --profile development --platform ios` for device integration; `eas build --profile production --platform ios` then `eas submit --profile production --platform ios` for TestFlight after configuring Apple credentials. These operations have not been run. Android internal distribution uses the preview APK profile.

## Validation and remaining acceptance

`npm run typecheck --workspace @selery/mobile` passes. `npm run export --workspace @selery/mobile` generates iOS and Android Hermes bundles. These verify source compilation and bundling, not signed binary installation or device interaction. Expo dependency versions were checked against `expo@57.0.21/bundledNativeModules.json`.

Real-iPhone acceptance remains pending: pinch/pan/crosshair/450ms marker long-press, navigation, reconnect/offline behavior, SecureStore persistence and expiry, notification taps, and p95 chart response below 100ms with 2,000 bars. No signed build, TestFlight upload, push delivery, app-store deployment, or physical-device benchmark is claimed complete. Desktop retains broad historical research/ML comparison workflows; mobile currently provides compact chart research and context.
