# SELERY native app guide

## Stock conversations and chart

Open the research assistant, specify a stock, and tap **Start conversation**. A route's suggested symbol is only a prefill. Select an existing thread from **Saved conversations** to continue it; conversations are stored on the backend and keep their original stock. Create another conversation for a different symbol.

The native view keeps a compact touch chart above the scrollable transcript, with a composer below it. The chart shrinks while the keyboard is visible and supports 5m/1h/1D context. Foreground reads refresh dated chart/thread state without requesting an AI answer. Follow-ups send prior exchanges plus fresh context for the chart's interval. Messages include source citations, local/AI labels, pending/failed states and explicit errors. Failed sends retain the draft; retries are manual and use an idempotent request identifier.

Back navigation returns to the saved-thread list. Delete removes a thread and its messages from the active backend database. Screen data clears on blur/background; no new persistent mobile cache is used. The existing activity-ID route remains the separate public-trader evidence chat. Native exports/type checks do not establish iPhone keyboard, chart gesture or layout acceptance; those checks remain pending.

## Public Traders

Open **Settings → Public Traders**. Native directory and activity cards share source filters, search and pagination, with additional symbol and inclusive UTC opening-date activity filters. Refresh the directory to import one provider page; select a trader and refresh their activity explicitly. Kinfo and AfterHour stay visibly pending while access is unresolved.

**View research details** opens a native route showing source identity, direction, unclassified exposure, entry/allocation, unknown quantity/exit, separate timestamps and limitations. Source prices have no assumed currency. The locally bundled touch chart supplies dated IEX context with TradingView attribution; it is not a trader's realized performance and may not include an old opening date. **Ask about this trade** opens activity-scoped chat with citations and permission-aware local/AI labeling. Public activity does not create a journal entry.

Routes are `/traders`, `/public-activity/[id]` and `/chat?activity_id=…`; a signed-in session is required. Public records and activity-chat answers clear on blur/background and are not persisted for offline viewing. Pull to refresh re-reads stored evidence; the explicit provider-refresh button is the action that fetches new public snapshots. Existing market cache behavior remains separate.

No new Expo permissions or mobile provider keys are needed. Use the existing Expo Go setup and `EXPO_PUBLIC_API_URL`; all eToro/OpenAI credentials remain on the backend. Push integration is not part of Public Traders. EAS/signing/TestFlight requirements below are unchanged. Bundle checks do not establish real-iPhone gestures, deep-link or real-record acceptance, which remain pending.

See [setup requirements](SETUP-REQUIREMENTS.md) and [public source qualification](docs/PUBLIC-TRADERS.md) for missing access and live LLM evidence. This feature is present on both surfaces; desktop-only broader research features are still identified below.

The native app is an Expo Router/React Native companion for reviewing market context, charts, alerts and personal notes. It uses the same authenticated Python research API and generated contracts as the web app. Its chart is a locally bundled renderer inside a WebView; navigation, forms and signal sheets are native.

**Selery is research software that displays analysis. It does not execute, recommend, or place trades.**

See [SETUP-REQUIREMENTS.md](SETUP-REQUIREMENTS.md) for every account, key and cost, and [WEB-GUIDE.md](WEB-GUIDE.md) for the broader desktop research interface.

## 1. Current delivery state

Implemented: Expo SDK 57/React Native 0.86 app source, six native tabs, research chat, local chart assets, SecureStore sessions, validated last-known response cache, ticketed reconnecting stream, native signal sheets, deep links, explicit journal saves and opt-in server device registration. EAS development, preview and production profiles are checked in.

TypeScript and iOS/Android JavaScript exports validate compilation and asset bundling. They do **not** establish a signed install, a TestFlight upload, physical-device gesture behavior or push reception. Real-iPhone acceptance remains pending until there is device evidence. The project does not claim that a headless browser timing measurement passes an iPhone interaction target.

## 2. Run locally with Expo Go

Prerequisites:

- Project dependencies installed with `npm ci` from the repository root.
- Python API dependencies installed with `uv sync --frozen --group dev`.
- Your existing backend `.env` with the personal login and Alpaca configuration.
- An Expo Go release that supports the project's SDK. If the installed Expo Go cannot run that SDK, use a compatible development build rather than changing dependencies ad hoc.
- Computer and phone on a network where the phone can reach the backend.

Start the API so it is reachable from the local network:

```sh
PYTHONPATH=apps/api:packages/shared/python:packages/strategies/python uv run uvicorn selery_api.main:app --host 0.0.0.0 --port 8000
```

Find your computer's Wi-Fi/LAN address in system network settings. In another terminal:

```sh
EXPO_PUBLIC_API_URL=http://YOUR_COMPUTER_LAN_IP:8000 npm run mobile
```

Replace the example address. Scan the Expo QR code on the phone and open the app. Sign in with `SELERY_PASSWORD`; never enter your Alpaca key into a client form.

The `mobile` command first bundles the local chart, then starts Metro/Expo. No chart CDN is loaded by the WebView. The shared renderer and chart font assets are packaged with the project.

A phone cannot reach your computer through `http://localhost:8000`. Check `http://YOUR_COMPUTER_LAN_IP:8000/health` from the phone's browser before troubleshooting the app. Allow local network access when prompted. A Metro tunnel only solves the Metro connection; it does not automatically expose your FastAPI backend.

Local HTTP is intended for the development network. Use a reachable HTTPS API URL for remote or distributed builds. The app's iOS configuration allows local-network development; that is not a reason to ship a public unencrypted service.

## 3. Native screens

| Screen | Implemented use |
| --- | --- |
| Watchlist | SPY, QQQ, AAPL and NVDA reference prices, feed/freshness labels, refresh and chart navigation |
| Chart | Symbol/timeframe controls, candle chart, backend EMA/RSI context, capability limitations, recent signals and native detail sheet |
| News | Source-linked headlines, summaries, timestamp and symbols; backend sentiment where returned |
| Alerts | Research inbox, read state and symbol/signal navigation |
| Journal | Manually authored thesis/outcome/reflection and explicit Save entry |
| Settings | API endpoint, data mode/feed, LLM cap/state, notification registration and sign out |
| Research chat | Source-linked local/optional LLM response with response mode and cost |

Most list screens support pull-to-refresh and show their loading, cached and error state. The app favors compact review; the desktop keeps the large historical research report, comparison and metadata workflows.

### Watchlist and data labels

Tap a symbol to open its chart. The same initial four-symbol universe is shared with the backend and web client.

**IEX only** identifies the venue-limited feed beside price/volume values. Do not treat it as NBBO or consolidated market volume. **Stale historical data** or **cached** means last-known observations, not a live quote. **Synthetic fixture** identifies generated test examples when present. Fixture mode usually serves recorded real provider observations that are still old today.

The watchlist uses the authenticated API and shared stream reconnect behavior. Failed connections keep their limitation visible. Returning to a cached screen does not update a price by itself; pull to refresh when you reconnect.

### Chart and signal sheet

Choose **5m**, **1h** or **1D**. The API explicitly requests IEX for this native workflow. Charts use shared Lightweight Charts rendering, with Python-produced candle/indicator/signal data.

Implemented gesture handlers:

- Drag horizontally to pan.
- Pinch to zoom.
- Use chart crosshair interaction to inspect a time/price point.
- Hold a signal marker to open the native sheet; marker long-press recognition is approximately 450 ms.
- Tap a signal card below the chart as an accessible alternative to locating a small marker.

The native sheet shows symbol, direction, strategy/version, source/feed, timestamps, reference level, analytical stop/target, horizon and confidence availability. It shows uncalibrated confidence as unavailable. The chart footer retains TradingView attribution.

These handlers are implemented but still require physical-iPhone validation, especially conflict between chart gestures and surrounding scrolling. Do not mark them accepted based only on an Expo export.

### Data capabilities

The chart shows backend-disabled features with their reason. VWAP, anchored VWAP, OBV, volume profile and related research requiring consolidated volume remain **“needs SIP data”** on IEX. The app does not unlock those by hiding a label or inventing volume.

The native chart is intentionally focused on the default research view. Desktop has indicator-layout presets, saved layouts, replay controls and the separate comparison chart. Those desktop controls are not automatically a native feature just because the renderer is shared.

### News and assistant

News links open the original source. The backend performs transparent lexical scoring and duplicate clustering; it does not prove a headline caused a price move. Publication time and retrieval/availability are different concepts.

Open the assistant from Settings. Specify a symbol and ask a question. Local mode gives an explicitly limited source-linked summary of available data. Optional LLM mode uses OpenAI GPT-5.6 Terra with high reasoning and requires all backend enablement, key and budget settings. The response shows its mode and cost allowance. Native chat sends a single research request; the multi-perspective debate control is a desktop feature. Changing the backend model does not require a native rebuild.

### Journal

Write your own thesis, observed outcome and reflection, then tap **Save entry**. Only that action sends the write. Browsing charts, receiving an alert or asking the assistant does not save a journal entry. A successful save updates the list from the backend record.

The current mobile form creates manual entries. Full editing, deletion, attachments and rich historical organization are not implemented as native workflows. Backend journal durability depends on the database/volume configuration, not SecureStore or the phone's cache.

## 4. Authentication, local data and offline behavior

The app stores an expiring session token in Expo SecureStore. It does not persist the workspace password or any provider key. The session expires after one hour; reauthenticate when required.

AsyncStorage keeps schema-validated last-known API responses and retrieval timestamps. Cache keys include the API endpoint so separate backends do not share the same local resource cache. The chart drops late responses when you switch symbol/timeframe. Shared cache rules keep stale or invalid data from silently masquerading as a successful refresh.

Offline behavior:

1. Previously visited resource data can remain available from cache while a valid local session exists.
2. Loading/error/cached status remains visible; no artificial live prices are generated.
3. A fresh sign-in needs the backend. An expired/revoked session is not restored by cached market data.
4. Reconnect attempts use short-lived single-use stream tickets and bounded backoff.
5. Sign out deletes the stored token and SELERY response cache. Signing out is the intended way to clear data on a shared device.

The local WebView document includes its chart script and a restrictive content policy. It receives research data from native code; it does not fetch provider credentials or external chart scripts. This improves offline rendering, but does not make every native screen fully usable without prior data or authentication.

## 5. Deep links and alert navigation

The app scheme is `selery`:

```text
selery://chart?symbol=SPY
selery://chart?symbol=SPY&signal=SIGNAL_ID
```

A symbol link opens the corresponding chart. A signal link opens the matching signal when it exists in the loaded response; an absent signal is not fabricated. A notification payload uses the symbol and optional `signal_id` to navigate to the same screen.

For manual development testing, after installing a development build:

```sh
npx uri-scheme open 'selery://chart?symbol=SPY' --ios
```

The URI scheme tool is optional; normal alert/notification taps are the primary workflow. Deep links must be checked on the actual installed build, since Expo Go has its own launch URL handling. Verify both already-running and cold-start cases.

## 6. Configure an Expo/EAS project

Use your own Expo account and project. From `apps/mobile`:

```sh
npx eas-cli login
npx eas-cli init
npx eas-cli build:configure
```

The app uses dynamic `app.config.ts`, so record the resulting EAS project ID in the expected environment rather than assuming every CLI can rewrite the config automatically. Keep the existing development/preview/production profiles unless deliberately changing the build design. [Expo EAS CLI reference](https://docs.expo.dev/eas/cli/)

Set these public/build values in the EAS environment and local shell/app environment as appropriate:

| Variable | Value you supply |
| --- | --- |
| `EXPO_PUBLIC_API_URL` | Your deployed HTTPS API origin |
| `EXPO_PUBLIC_EAS_PROJECT_ID` | Expo project UUID |
| `SELERY_IOS_BUNDLE_ID` | Unique Apple bundle identifier |
| `SELERY_ANDROID_PACKAGE` | Unique Android package identifier |

These are app configuration values, not a place for Alpaca, OpenAI, SMTP or other provider secrets. Public values become part of the client build. Changing the API URL in the server `.env` does not rewrite an already exported native bundle; rebuild/re-export with the new app environment.

Before a cloud build, ensure the generated chart HTML reflects the shared renderer:

```sh
npm run chart:bundle
npm run typecheck
```

Run those two commands inside `apps/mobile`, or use their workspace variants from the root. Commit the intentional updated generated chart asset together with related renderer changes before the cloud build. Metro uses the monorepo's shared source. [Expo monorepo guidance](https://docs.expo.dev/guides/monorepos/)

## 7. Development, preview and production builds

The checked-in `eas.json` defines:

| Profile | Purpose |
| --- | --- |
| `development` | Development client, internal distribution; use for native integration and push checks |
| `preview` | Internal distribution; Android emits APK, iOS targets a physical device rather than a simulator |
| `production` | Release build with remote version incrementing |

From `apps/mobile`:

```sh
npx eas-cli build --profile development --platform ios
npx eas-cli build --profile development --platform android
```

After installing your development client, run Metro for that client:

```sh
npm run chart:bundle
npx expo start --dev-client
```

Pass `EXPO_PUBLIC_API_URL` in that shell or set its app-level environment first. The development client still needs a reachable backend.

For an Android internal APK:

```sh
npx eas-cli build --profile preview --platform android
```

Install the produced APK on your test device. Internal APK distribution does not require publishing to Google Play. For an iOS internal build, the test device must be eligible under your Apple provisioning arrangement. [Expo internal distribution](https://docs.expo.dev/build/internal-distribution/)

No cloud build in these instructions has been performed merely because the profiles exist. EAS quota/credits and platform signing are external prerequisites.

## 8. Apple/TestFlight requirements

You need:

- An Apple ID enrolled in the Apple Developer Program.
- Your team identifier and the intended app bundle identifier.
- Signing certificates/provisioning or permission for EAS to manage them.
- An App Store Connect app record with the same bundle identifier.
- An App Store Connect authentication method for upload, such as a scoped API key managed through EAS; keep the private key out of Git.
- A device and TestFlight tester access.
- Appropriate app metadata, icon/artwork and any required privacy/export-compliance answers based on the actual app.

Apple Developer membership is $99 USD/year, with regional differences. [Apple enrollment](https://developer.apple.com/programs/enroll/)

After development-device acceptance, build and submit from `apps/mobile`:

```sh
npx eas-cli build --profile production --platform ios
npx eas-cli submit --profile production --platform ios
```

Select the intended build during submission. Complete App Store Connect processing/compliance prompts and add your internal testers. A submitted binary is not the same thing as a successful TestFlight install; record both results.

The existing configuration includes a default bundle ID and encryption declaration. Validate these against your own signing identity and the final app before distribution. Final store artwork and publishing metadata remain your supplied resources, not inferred identities.

## 9. Push notification setup

Expo Go supports initial browsing, but this app blocks remote push registration there. Use a development/distribution build and a physical device. Expo likewise directs SDK 53+ push testing to a development build. [Expo push FAQ](https://docs.expo.dev/push-notifications/faq/)

Required:

1. EAS project ID and platform signing.
2. APNs key/entitlements for iOS, or FCM v1 setup for Android, stored through the appropriate credential management flow.
3. User notification permission on the device.
4. An authenticated **Register this device** action in Settings.
5. Backend `SELERY_NOTIFICATIONS_ENABLED=true` when you intentionally enable delivery.
6. Optional backend `EXPO_ACCESS_TOKEN` if your Expo push setup requires enhanced access control.

Registration obtains an Expo push token and posts it to the authenticated research backend. It does not itself send a notification or enable all server delivery channels. The backend can disable a registration and preserves delivery state. Notification provider acceptance is not evidence that a device displayed the alert. [Expo push setup](https://docs.expo.dev/push-notifications/push-notifications-setup/)

Acceptance sequence:

- Install the development build and sign in.
- Register the device and confirm the backend registration result.
- Intentionally enable the server delivery channel.
- Generate or select an actual authorized research-alert test case; do not label fabricated content as market evidence.
- Check provider ticket/receipt status, foreground/background presentation, and physical reception.
- Tap the notification and verify symbol/signal navigation from both running and cold states.
- Deny permission or disable a device and check the app's explicit unavailable state.

Unknown delivery results are not automatically retried, avoiding duplicate sends after a timeout. Receipt reconciliation must be scheduled/verified in the deployed environment. Discord, Telegram and email use backend-only settings listed in the setup guide; those tokens never belong in the mobile app.

## 10. Web versus native coverage

| Capability | Native | Desktop web |
| --- | --- | --- |
| Personal login and feed-labelled watchlist | Yes | Yes |
| Candle chart and signal details | Native sheet + touch renderer | Detail panel + mouse/keyboard renderer |
| Default 5m/1h/1D views | Yes | Yes |
| Shared Python calculations/contracts | Yes | Yes |
| Source-linked news and research chat | Yes | Yes |
| Manual journal creation | Yes | Yes |
| Alert inbox and deep links | Yes | Yes, symbol navigation |
| Push device registration | Development/distribution builds | No native device registration UI |
| Historical report form/metrics/JSON export | Desktop workflow | Yes |
| Outcome cohort table | Desktop workflow | Yes |
| Informational sizing form | Desktop workflow | Yes |
| Saved indicator layouts, replay, comparison chart | Desktop workflow | Yes |
| Full model/domain metadata view | Compact connection/LLM settings only | Yes |
| Multi-perspective LLM control | Single-request chat | Optional funded comparison |

An API feature shared across clients is not automatically a visible native screen. The app deliberately does not replicate every dense desktop form.

## 11. Build checks and real-device acceptance

From the root:

```sh
npm run typecheck --workspace @selery/mobile
npm run export --workspace @selery/mobile
```

Export bundles both iOS and Android JavaScript/assets and regenerates the local chart. No Apple/Google signing credential is required just to export JavaScript. EAS builds and actual installs are separate checks.

Before mobile acceptance, record device model, OS, build/profile and API/data mode, then verify:

- Login, SecureStore persistence, one-hour expiry and sign out/cache clearing.
- Every tab, back navigation, keyboard behavior and readable error states.
- IEX badges beside quotes/volume and disabled SIP-dependent capabilities.
- Pinch, pan, crosshair and long-press with a native detail sheet.
- Touch response p95 below 100 ms with 2,000 displayed bars, using a reproducible device measurement.
- Reconnection after Wi-Fi loss, cached labels, recovery and symbol-switch race handling.
- Explicit journal save, with no write from a chart/chat action.
- Link opening and symbol/signal deep links.
- Opt-in push permission, registration, provider receipt, physical reception and notification navigation.

The shared renderer's desktop test benchmark does not meet the device requirement by itself. Real-device evidence is still required even if both platform bundles compile.

## 12. Troubleshooting

| Symptom | Likely check |
| --- | --- |
| Phone cannot connect | Use computer LAN IP, API `0.0.0.0`, same Wi-Fi, local firewall and local-network permission |
| Metro loads but API fails | Metro tunnel/QR access and backend reachability are separate |
| Expo Go says SDK incompatible | Install compatible Expo Go where supported or create an EAS development client |
| Chart is blank after shared changes | Regenerate `chart-html.ts` with `chart:bundle`, restart Metro, inspect native WebView errors |
| Chart data is old | Fixture mode, cache state, source timestamp and backend/provider availability |
| VWAP says needs SIP data | Correct IEX restriction; OPRA/SIP upgrades need backend entitlement, not a client key |
| Login fails after an hour | Session expired; sign in again |
| Push registration refuses Expo Go | Expected; install a development build |
| Push project ID missing | Set `EXPO_PUBLIC_EAS_PROJECT_ID` before building/config evaluation |
| Device registered but no notification | Server delivery may still be off; check signing, permission, tickets and receipts |
| Deep link lacks the signal | The requested signal may not be in the current response; verify symbol/ID and archival availability |
| Fresh offline launch has no data | A valid session and previously cached resource are required; no artificial fallback exists |
| New API URL is ignored | Rebuild/re-export with the mobile public environment; changing only the server environment is insufficient |

For the latest integration status and unfinished external requirements see [PROGRESS.md](PROGRESS.md), [DEBT.md](DEBT.md) and the wave reviews. Do not interpret this guide's build commands as evidence that a distribution action has already occurred.

## Final integration notes

The native chart requests a bounded 400-bar response through the shared client; the desktop defaults to 1,000 and the API accepts 80–2,000. Both still use the canonical chart shape, rather than a separate mobile projection. List schema construction lives in the shared package, avoiding incompatible Zod type composition while retaining runtime validation. The local mobile TypeScript check now completes using roughly 380 MiB with the default heap.

A successful iOS/Android JavaScript export is recorded in [verification](reviews/verification.md). It is not a signed native build or real-device acceptance. See [coverage](docs/REQUIREMENT-COVERAGE.md) for native features that remain incomplete.
