# Track H — portable state and optional alert delivery

Adds authenticated device registration, opt-in backend delivery for existing research alerts, and receipt reconciliation. No notification is sent by registration, route installation, tests, or module import. Delivery stays disabled unless `SELERY_NOTIFICATIONS_ENABLED=true` and a caller explicitly invokes `deliver_alert`.

## Integration

Call `register_routes(app, authorized)` inside API `create_app` after defining its auth dependency. Routes are POST `/api/v1/notifications/devices` (`DeviceRegistration` → `DeviceRegistrationResult`), POST `/api/v1/notifications/devices/{identifier}/disable`, and GET `/api/v1/notifications/status`. Canonical device models belong to Python shared contracts and are generated into TypeScript. Device tokens remain in the protected database; responses and audit records contain hashes/status only.

When notifications have explicitly been configured, the existing observer/worker may call `await deliver_alert(store, alert_id)` for a persisted alert, followed by `await reconcile_receipts(store)` around 15 minutes later. Delivery makes an atomic per-alert/channel/recipient claim in the existing settings collection, preventing duplicate requests across workers or restarts. An interrupted/uncertain result remains `unknown` and is not automatically resent; this favors avoiding duplicates over guaranteed delivery. Provider rejection is `failed`, Expo queue acceptance is `accepted`, and a successful push receipt is `provider_delivered`, which still does not prove that a user saw the notification. A missing receipt remains pending. DeviceNotRegistered disables a token unless it was re-registered after the delivery attempt.

Optional server-only environment variables: `EXPO_ACCESS_TOKEN`; `SELERY_DISCORD_WEBHOOK`; `SELERY_TELEGRAM_BOT_TOKEN` and `SELERY_TELEGRAM_CHAT_ID`; `SELERY_SMTP_HOST`, `SELERY_SMTP_PORT` (587), `SELERY_SMTP_USER`, `SELERY_SMTP_PASSWORD`, `SELERY_SMTP_FROM`, `SELERY_SMTP_TO`, `SELERY_SMTP_TLS` (`starttls` or `ssl`). SMTP always uses TLS. Discord accepts standard discord.com HTTPS webhook URLs only and suppresses mentions. Notifications carry research title/body plus symbol/signal identifiers. Mobile provider credentials remain absent.

## Shared client state

`@selery/shared/src/cache` exports `encodeCache` and `parseCache`: schema validation, corruption/unknown-version rejection, legacy mobile envelope compatibility, timestamp validation, TTL freshness, and future-clock staleness. Platform wrappers own AsyncStorage/localStorage and should force stale display when a refresh fails.

`@selery/shared/src/stream` exports `connectResearchStream`: inject ticket retrieval, browser/native WebSocket factory, event/status handlers, and optional scheduler adapters. It validates generated StreamEvent schemas, refreshes single-use tickets per connection, reconnects with bounded 1–30 second exponential delays, and cancels subscriptions/pending connections on stop. Platform wrappers own React lifecycle only.

## Evidence and remaining acceptance

Fifteen deterministic backend tests cover auth, registration/deduplication, default-off operation, atomic claims, timeout ambiguity, ticket and receipt handling, token revocation/re-registration, optional channel mocks, and webhook validation. TypeScript helper tests cover cache schema/freshness/corruption and reconnect/single-use-ticket/stop behavior. All network calls in tests use httpx.MockTransport; SMTP is replaced by an offline stub.

Live registration, configured push/email/Discord/Telegram delivery, device receipt, and distribution credentials have not been verified. No messages were sent. The default app remains safe to run without these resources. Provider semantics follow [Expo’s server push documentation](https://docs.expo.dev/push-notifications/sending-notifications/).

Mobile integration: Settings should call `registerNotificationsWithServer(client)` instead of token-only `registerNotifications()` and display the returned enabled state. This wrapper uses the shared authenticated request path and generated response schema. The original token-only function remains available for explicit Expo tooling tests, while regular app registration should use the server wrapper.
