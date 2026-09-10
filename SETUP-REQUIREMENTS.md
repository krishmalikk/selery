# SELERY setup requirements

## Stock conversations — additional setup

No new account, API key, dependency or paid service is required. The existing OpenAI/Terra configuration and $5/month cap serve multi-turn stock conversations. Opening threads and refreshing charts do not spend LLM credits. The last live billing diagnosis was `credit_balance_exhausted`; new UI behavior does not fund the provider account.

SQLite creates `conversations` and `conversation_messages` automatically on backend startup. New Compose databases run migration 003. Existing PostgreSQL databases should apply `packages/shared/migrations/003_conversations.sql` after a backup: `docker compose exec -T db psql -U selery -d selery < packages/shared/migrations/003_conversations.sql`. Rebuild/restart the backend and web application; re-export mobile for the new routes/UI. Continue running one API process, since in-flight thread coordination follows the existing single-process runtime.

Conversation messages are private backend data and should be included in your existing backup/retention policy. Deleting a thread removes active database messages; old backups require separate retention handling. Saved history is capped at 200 messages per thread/500 threads; model context uses the newest bounded exchanges, with older text still readable in the app. See [stock conversation review](reviews/stock-conversations.md).

## Public Traders extension — September 9, 2026

**Latest local status:** Both `SELERY_ETORO_DATA_ALLOWED` and `SELERY_ETORO_LLM_ALLOWED` are enabled at the user's explicit request. Live imports returned 11 profiles and 122 open observations from one trader. The remaining OpenAI blocker is confirmed `credit_balance_exhausted`: add API credits in [OpenAI billing](https://platform.openai.com/settings/organization/billing/overview), then retry the assistant. SELERY's $5/month cap is unchanged and does not itself fund API credits. Default templates below remain opt-in. See [verification and diagnosis](reviews/etoro-enabled-openai-billing.md).

The code is available on both clients; eToro real import is verified locally, with real-iPhone acceptance pending. Kinfo/AfterHour remain unavailable. See [access qualification and implementation](docs/PUBLIC-TRADERS.md) and unsent [Kinfo](docs/access-inquiries/KINFO.md) / [AfterHour](docs/access-inquiries/AFTERHOUR.md) inquiries.

| Backend variable | Required value / purpose |
| --- | --- |
| `SELERY_PUBLIC_TRADERS_MODE` | `live` by default; `fixtures` only for explicitly synthetic development |
| `ETORO_API_KEY` or `ETORO_PUBLIC_KEY` | Application credential; supplied and accepted for the read-only metadata probe |
| `ETORO_USER_KEY` or `ETORO_PRIVATE_KEY` | User credential; supplied and accepted for the read-only metadata probe |
| `SELERY_ETORO_DATA_ALLOWED` | Default `false`; set `true` only after permitted private storage/display, refresh and removal terms are established |
| `SELERY_ETORO_LLM_ALLOWED` | Default `false`; separate permission to supply selected records to OpenAI |

Put these only in root `.env` locally or Railway API variables. Restart the backend after changing `.env`. Never use `NEXT_PUBLIC_` or `EXPO_PUBLIC_` for these values, and do not copy keys into Vercel or Expo. Vercel uses the existing server-side `SELERY_API_URL`; mobile uses its existing public backend URL and SecureStore login token. No additional database, Redis job, chart subscription or Vercel service is needed for this extension. Actual eToro feed price and live resource requirements remain unverified; no subscription is purchased. Kinfo and AfterHour need approved access agreements before any credentials or adapter can be specified.

Credential verification on 2026-09-09 returned HTTP 200 for instrument display metadata. Run `.venv/bin/python scripts/verify_etoro.py` for the same explicit, sanitized probe. It does not fetch public traders, store source records or call OpenAI. Public-record entitlement and data-use permissions remain pending. Use one variable name per credential; conflicting alias values fail closed. Evidence: [sanitized verification](docs/etoro-verification.json).

The existing OpenAI key and approved $5/month app allowance remain unchanged. Enabling source rights does not resolve the previously observed OpenAI HTTP 429; successful paid/cited output needs separate billing/rate-limit and model-access verification. Public-record summaries work locally without LLM access.

New databases run migrations 001 and 002 through Compose initialization. On an existing PostgreSQL database, apply `packages/shared/migrations/002_public_traders.sql` once (idempotently); for Compose, use `docker compose exec -T db psql -U selery -d selery < packages/shared/migrations/002_public_traders.sql`. Back up first. SQLite creates the new tables on API startup. Keep a single API process; public refresh throttling is process-local.

For an isolated preview, set `SELERY_PUBLIC_TRADERS_MODE=fixtures`, keep LLM disabled, restart the API, open Traders and manually refresh. Do not change existing live market configuration merely to preview the separate public registry. Synthetic examples never establish provider acceptance. Switch back to `live` for pending/authorized access; the fixture examples are hidden from live reads.

This is the account, credential, deployment and resource checklist for the implemented personal research workspace. The web walkthrough is in [WEB-GUIDE.md](WEB-GUIDE.md); the native walkthrough is in [MOBILE-GUIDE.md](MOBILE-GUIDE.md).

**Selery is research software that displays analysis. It does not execute, recommend, or place trades.**

## 1. What you already have and what is still needed

The existing root `.env` contains the Alpaca settings you supplied and generated local authentication settings. Keep that file; use [.env.example](.env.example) as a reference rather than copying over it. No actual credential value is included in this guide.

Authenticated market-data verification succeeded on September 9, 2026: recorded IEX bars for SPY, QQQ, AAPL and NVDA, older SPY SIP bars, and news. A separate live smoke recorded four quotes, 100 IEX bars, 30 news items and an authenticated IEX stream. See [Alpaca verification](docs/alpaca-verification.json) and [live smoke](docs/live-smoke.json). These checks do not establish paid real-time SIP or OPRA entitlement, and access can change with your account.

| To accomplish | You need |
| --- | --- |
| Run web locally using recordings | Python 3.12, uv, Node/npm matching the lockfile, the existing `.env`, and two local processes |
| Use live Alpaca data | Existing Alpaca credentials; set backend `SELERY_DATA_MODE=live` |
| Open native app on your iPhone | Expo Go compatible with the project SDK, same-network backend address, and your personal workspace password |
| Publish the web UI | A Git hosting repository, Vercel account/project, backend HTTPS address, and Vercel environment variables |
| Keep backend running remotely | Railway account/project, billing choice, persistent data volume, environment secrets, and measured resource budget |
| Run full database/worker stack | Docker Engine/Compose, database password, disk space, TimescaleDB and Redis containers |
| Install an iOS development build/TestFlight | Expo/EAS account and project ID, Apple Developer membership, bundle identifier, signing/provisioning and an App Store Connect app |
| Install an Android internal APK | Expo/EAS project or local Android toolchain, package identifier and Android signing key; a Play Store listing is not required |
| Receive external research alerts | Opt-in server setting plus credentials for your selected channel; phone push also needs native signing and permission |
| Enable LLM research | OpenAI API key, explicit enablement, positive monthly cap and current model/pricing settings |
| Run optional ML training | Larger suitable historical datasets, optional Python ML dependencies and manually allocated compute |

No Vercel deployment, Railway provisioning, paid subscription, cloud mobile build, TestFlight upload or physical-device acceptance is implied by the source code or local bundle checks.

## 2. Required software and the inexpensive local start

Use macOS/Linux commands below from the repository root. Install Python 3.12 through [uv](https://docs.astral.sh/uv/getting-started/installation/) if needed. Use a Node release supported by the pinned dependencies. React Native accepts Node 22.13+ in the 22 line or 24.3+ in the 24 line; this workspace was validated with Node 26.4.0. The root package declares `npm@11.17.0`. Python and JavaScript resolution is recorded in `uv.lock` and `package-lock.json`.

```sh
uv python install 3.12
uv sync --frozen --group dev
npm ci
```

Review the existing `.env` in your editor. Required backend values:

| Variable | Requirement |
| --- | --- |
| `ALPACA_ENDPOINT` | Exactly the HTTPS paper API host, `https://paper-api.alpaca.markets`. Startup rejects a live or unrecognized host. Actual market-data requests use Alpaca's data service. |
| `ALPACA_KEY` | Your Alpaca key; required for live data, not for replaying existing recordings. |
| `ALPACA_SECRET` | Matching Alpaca secret; same server-only handling. |
| `SELERY_PASSWORD` | Personal workspace login password, at least 12 characters. Use a password manager. |
| `SELERY_SESSION_SECRET` | At least 32 random characters. Keep stable across restarts; change it to invalidate existing signed sessions. |
| `SELERY_DATA_MODE` | `fixtures` initially; `live` for current market data. |
| `SELERY_DATABASE_URL` | Default `sqlite:///./data/selery.db`; relative to the root when using the commands below. |
| `SELERY_ALLOWED_ORIGINS` | Comma-separated exact browser origins, without trailing slashes, e.g. `http://localhost:3000,http://127.0.0.1:3000`. Add your production web origin when deploying. |

Terminal 1, API:

```sh
PYTHONPATH=apps/api:packages/shared/python:packages/strategies/python uv run uvicorn selery_api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, web:

```sh
npm run dev
```

Open `http://localhost:3000` and enter the personal password from your local configuration. `/health` on port 8000 reports backend readiness. This SQLite path needs no separate database server or Redis. Recorded data is intentionally stale; a successful recording view is not proof that current data is arriving.

For an iPhone on your Wi-Fi, run the API with `--host 0.0.0.0` and start Expo with a **public address only**:

```sh
EXPO_PUBLIC_API_URL=http://YOUR_COMPUTER_LAN_IP:8000 npm run mobile
```

Replace `YOUR_COMPUTER_LAN_IP` with the computer's network address. A phone's `localhost` points to the phone. Local HTTP is for the private development network; use HTTPS/WSS for deployed access.

## 3. Where each environment value belongs

| Location | Values to place there |
| --- | --- |
| Root `.env` | Backend local secrets, data mode, database, origins and optional provider/alert/LLM settings |
| Railway API variables | Production equivalents of backend values; provider keys stay here |
| Railway worker variables | Same database, Redis and necessary backend settings if you deploy a worker |
| `apps/web/.env.local` or Vercel variables | `SELERY_API_URL`; optional `NEXT_PUBLIC_SELERY_WS_URL` |
| `apps/mobile/.env.local`, shell or EAS environment | `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_EAS_PROJECT_ID`, identifiers used while evaluating the Expo app config |
| Expo/EAS credential storage | Apple certificates/APNs key, provisioning profiles, Android keystore and FCM credentials |
| GitHub Actions secrets, if deploying from CI | Only deployment tokens needed by that workflow; no such external deployment is required for local tests |

Next and Expo run from nested app folders. Do not assume they automatically read the repository-root `.env`; set their small, explicit configuration where listed. Never copy the entire backend `.env` into a client project. `NEXT_PUBLIC_*` and `EXPO_PUBLIC_*` are visible to users in the downloaded application.

Web variables:

- `SELERY_API_URL`: backend origin, e.g. `https://your-api.up.railway.app`. Server-side only.
- `NEXT_PUBLIC_SELERY_WS_URL`: optional `wss://your-api.up.railway.app/api/v1/stream`. Without it, the web UI polls every 30 seconds. Use the same backend as the REST proxy.

Mobile variables:

- `EXPO_PUBLIC_API_URL`: reachable API origin, without `/api/v1`.
- `EXPO_PUBLIC_EAS_PROJECT_ID`: your project's UUID from Expo; public identifier, not a credential.
- `SELERY_IOS_BUNDLE_ID`: choose your unique bundle identifier; the code defaults to `com.selery.research`.
- `SELERY_ANDROID_PACKAGE`: choose your Android package; same default.

## 4. Vercel web deployment

1. Put the repository in your own Git host and connect it to Vercel. Existing local worktrees are implementation branches, not remote deployments.
2. Import the repository with **Next.js** as framework and **`apps/web`** as Root Directory.
3. Enable inclusion of files outside the root directory so `packages/shared` and the root lockfile are available. Next already transpiles `@selery/shared`. [Vercel monorepo setup](https://vercel.com/docs/monorepos/monorepo-faq)
4. Use the workspace lockfile: install command `cd ../.. && npm ci`; build command `cd ../.. && npm run build --workspace @selery/web`. Leave the framework's `.next` output convention in place.
5. Add `SELERY_API_URL` and, if wanted, `NEXT_PUBLIC_SELERY_WS_URL` to the intended Preview/Production environments. Add the resulting web origins to the API allowlist. Preview origins are separate from the production origin.
6. Deploy, then test login, quotes, chart, research, explicit journal save and sign out. Check that a valid session cookie is HttpOnly and Secure over HTTPS.
7. Verify direct WebSocket origin acceptance separately. Vercel serves the web/proxy; the persistent backend owns the stream.

A custom domain is optional; the provided Vercel/Railway domains are enough. Domain registration is a separate cost. Hosted acceptance remains pending until these steps produce real deployment evidence.

## 5. Railway and database options

The root `Dockerfile` packages the Python API and shared packages. `railway.toml` selects it and uses `/health` as the health check. Railway supplies `PORT`; the container listens on it.

For the initial personal deployment, use **one API replica/process** with SQLite on a persistent volume mounted at `/app/data`. Set `SELERY_DATABASE_URL=sqlite:////app/data/selery.db`. Make sure the non-root container user can write to the volume. Store raw archives and model artifacts on the same persistent volume. Without it, a redeploy can discard journals and research records.

The current session revocation/ticket state is process-local. Multiple API replicas are not a supported configuration until that state is shared. Scaling is not a substitute for measuring the single-user workload.

For full local services, set `SELERY_DB_PASSWORD` to a separate generated password and run:

```sh
docker compose up --build
```

`compose.yaml` provides TimescaleDB/PostgreSQL, Redis, API and one Arq worker. Named volumes retain database, Redis and raw data. Initial SQL migrations are mounted for a new database. They do not automatically replay on an existing database volume. Avoid deleting volumes as a troubleshooting shortcut.

Additional settings:

| Variable | Purpose |
| --- | --- |
| `SELERY_DB_PASSWORD` | Compose PostgreSQL password. Use a URI-safe generated value or account for URL encoding. |
| `SELERY_REDIS_URL` | Redis URL for the Arq worker; Compose supplies `redis://redis:6379`. |
| `SELERY_DATABASE_URL` | A `postgresql+psycopg://...` URL when using PostgreSQL. Compose supplies its internal connection. |

The normal web research request currently runs against the API directly. Arq exposes a manual research job function and the optional `POST /api/v1/jobs/research` enqueue route; simply starting the worker does not turn every normal web request into a queued job. Scheduled training is disabled. Docker service startup and managed Timescale deployment need separate environment verification.

For backups, snapshot the persistent volume or use a consistent SQLite backup while the service is stopped/using the SQLite backup API; use PostgreSQL's backup tools for PostgreSQL. Also retain raw archives and model metadata. Perform a restore test before relying on hosted journals.

## 6. Optional research data resources

The default watchlist/chart path stays Alpaca. Alternate adapters are explicit requests and never a silent fallback. Configuration availability does not prove account entitlement or data freshness.

| Source | Backend value/resource | Implemented support and limits |
| --- | --- | --- |
| Alpaca IEX | Existing Alpaca settings | Quotes, bars, news, authenticated stream; default forward feed. IEX volume features remain disabled. |
| Alpaca historical SIP | Existing credentials plus verified entitlement | Explicit older historical SIP requests; recorded verification succeeded. The adapter ends at least 16 minutes before retrieval. This does not grant real-time SIP. |
| Finnhub | `FINNHUB_API_KEY` | Quote/candle adapter. Candle availability depends on the account plan. |
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` | Compact raw daily history, up to the provider's compact window; quota failures remain errors. |
| Twelve Data | `TWELVE_DATA_API_KEY` | Explicit 5m/1h/daily series. Coverage/delay remain unverified unless established. |
| FRED/ALFRED | `FRED_API_KEY` | Economic observations at an explicitly requested vintage date. Intraday release time is a separate requirement. |
| SEC EDGAR | `SEC_USER_AGENT` such as an application name followed by your own contact email | Read submissions/company facts and named official feeds; no API key required for these public sources. |
| Kenneth French library | No API key | Daily three-factor ZIP reader. Historical publication vintage is not established; use as retrospective context. |
| yfinance | Optional Python package and explicit adapter enablement | Personal-use daily historical SDK adapter. Adding a key does not enable it; the default API factory remains disabled. |
| Massive | Vendor account/key, entitlement and deliberate adapter wiring | Paid historical bar adapter exists; no active paid route or automatic enablement. |
| Databento | Vendor key, dataset name, entitlement, optional SDK and manual wiring | Paid daily historical adapter exists; no active paid route or automatic enablement. |
| Current SPY issuer file/NAV | Dated issuer source files with availability metadata | Calculation helpers exist. Default domain view shows missing current holdings/NAV honestly. |
| OPRA/options | Entitled source, timestamps, underlying/IV/expiry inputs | Pure options context helpers exist; equity SIP does not imply OPRA. No live options subscription is configured. |

Provider-specific API keys belong in your own provider dashboards and server environment, not in a chat message. The free-provider query endpoint and provider catalog describe supported requests. Paid adapter objects deliberately require more than merely placing a token in `.env`.

IEX restrictions include VWAP, anchored VWAP, OBV, volume profile, unusual-volume signals and any strategy/alpha formula that needs consolidated volume. The backend rejects such calculations with **“needs SIP data.”** Historical SIP and forward IEX cohorts must not be combined as if they used the same feed. [Alpaca feed documentation](https://docs.alpaca.markets/us/docs/market-data-faq)

## 7. LLM configuration and costs

Local source-linked explanations work without an LLM. They summarize the available symbol data and cannot answer arbitrary questions. The optional implementation uses OpenAI's Responses API with GPT-5.6 Terra and high reasoning. Create a backend-only API key in your OpenAI project and enable API billing/model access; a ChatGPT subscription does not configure this application.

| Variable | Default / meaning |
| --- | --- |
| `OPENAI_API_KEY` | Empty; `OPENAI_KEY` and `openAI_KEY` aliases also work. Set one key value; conflicting aliases are rejected. |
| `SELERY_LLM_ENABLED` | `false` |
| `SELERY_LLM_MONTHLY_CAP_USD` | `0`; calls remain disabled until positive |
| `SELERY_LLM_MODEL` | `gpt-5.6-terra` |
| `SELERY_LLM_REASONING_EFFORT` | `high` |
| `SELERY_LLM_MAX_OUTPUT_TOKENS` | `8192`, including hidden reasoning and visible output; accepted range 256–32768 |
| `SELERY_LLM_INPUT_USD_PER_MILLION` | `2` for the configured model |
| `SELERY_LLM_OUTPUT_USD_PER_MILLION` | `12` for the configured model |

These prices match the checked Terra base token rates; verify them again if changing the model or enabling billing later. Cached inputs are conservatively accounted at the full input rate, so the displayed allowance can exceed the provider invoice. Reasoning tokens count once as output usage. [OpenAI Terra documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra)

To enable locally, set the key, `SELERY_LLM_ENABLED=true` and your chosen positive `SELERY_LLM_MONTHLY_CAP_USD` in root `.env`, then restart FastAPI. For Railway, set these in the backend service variables and redeploy. The local user approved a $5/month cap on September 9, 2026; the committed template remains disabled at $0. The cap covers this SELERY database's usage, not other applications using the same OpenAI account.

Requests use `store=false` and contain only the supplied research context with no external tools. An exhausted reasoning/output limit returns an explicit incomplete-response error and records reported usage; it never automatically retries a paid request. The 8192-token limit is a budget/latency choice, not a guarantee that every high-reasoning question will complete. [OpenAI reasoning guidance](https://developers.openai.com/api/docs/guides/reasoning)

The server reserves a conservative allowance atomically before each request. It records feature usage, keeps uncertain requests reserved without automatic retries, and enables a persistent kill switch if observed usage exceeds the reservation. Settings show spent plus reserved usage. A provider error can therefore leave budget unavailable until a human reconciles the bill. Changing model prices without updating the settings invalidates the budget assumption.

Perspective comparison is manual and runs four analytical roles plus a synthesis call. That takes more time/cost than a single response. The chat proxy allows up to 285 seconds and the server limits each provider call to 45 seconds; your hosting plan may impose a lower ceiling. Do not repeatedly click after an uncertain response, since a request may still be running. Production queued long-job handling remains an operational limitation. No LLM action changes journals or invokes external execution tools.

## 8. Optional alert delivery

The inbox works without external messaging. Delivery is off until `SELERY_NOTIFICATIONS_ENABLED=true` and the chosen destination is configured.

| Channel | Required server settings/resources |
| --- | --- |
| Expo push | Registered native device; EAS project, platform push credentials and permission. `EXPO_ACCESS_TOKEN` if using Expo's enhanced push security. |
| Discord | `SELERY_DISCORD_WEBHOOK` for the intended channel |
| Telegram | `SELERY_TELEGRAM_BOT_TOKEN` and `SELERY_TELEGRAM_CHAT_ID` |
| Email | `SELERY_SMTP_HOST`, `SELERY_SMTP_PORT`, `SELERY_SMTP_FROM`, `SELERY_SMTP_TO`; authenticated providers also need `SELERY_SMTP_USER` and `SELERY_SMTP_PASSWORD` |
| SMTP encryption | `SELERY_SMTP_TLS=starttls` (typically port 587) or `ssl` (typically 465) |

Opt-in sends use existing research alerts. A durable per-alert/channel/recipient claim prevents blind retries after an unknown result. Provider acceptance does not prove that you saw a notification. Receipt reconciliation exists as a service helper; scheduling/observing delivery must be verified for your deployment. Never put a Discord webhook, Telegram token or SMTP password in the app.

For iPhone push use an EAS development build; the app blocks registration in Expo Go and requires a physical device for its acceptance workflow. [Expo push setup](https://docs.expo.dev/push-notifications/push-notifications-setup/)

## 9. Cost target and what requires more resources

| Resource | Starting cost/decision |
| --- | --- |
| Local web/API/native preview | No hosting subscription; uses your computer |
| Vercel Hobby | Free for eligible personal, non-commercial use, within plan limits. [Vercel Hobby](https://vercel.com/docs/plans/hobby) |
| Railway Hobby | $5/month plan includes $5 of usage; usage above that adds cost. [Railway pricing](https://railway.com/pricing) |
| Expo/EAS | Free plan offers a limited quantity of lower-priority builds; check quota before building. [Expo plans](https://docs.expo.dev/billing/plans/) |
| Apple Developer | $99 USD/year, regional pricing may vary; separate from the hosting target. [Apple enrollment](https://developer.apple.com/programs/enroll/) |
| Custom domain | Optional annual registrar cost |
| Data upgrades | Optional account-dependent subscription/usage costs; none purchased |
| LLM | Default $0/disabled; separate explicit cap when enabled |

Approximately $5/month is a target for a minimal personal backend, **not a measured guarantee for the full TimescaleDB + Redis + API + worker stack**. Scientific dependencies and model training consume memory. Start with one persistent API service or keep it local, observe memory/CPU/storage/egress, and record measured usage before adding hosted services or raising limits. Keep training/manual historical jobs on local compute until measurements justify another deployment. No scheduled retraining or paid data retrieval is automatically enabled.

## 10. Verification and remaining external acceptance

Run offline checks from the root:

```sh
npm run typecheck
npm run build
npm run export --workspace @selery/mobile
uv run pytest
npm run test:security
npm run contracts
git diff --exit-code -- packages/shared
```

Browser checks require the local API and web servers running:

```sh
npx playwright install chromium
npx playwright test
```

Live provider verification is separate from tests:

```sh
uv run python scripts/verify_alpaca.py
PYTHONPATH=apps/api:packages/shared/python:packages/strategies/python uv run python scripts/smoke_live.py
```

The verification script records fixtures/evidence; it is not an offline unit test. It performs approved market-data reads and sanitized reporting. Do not run it just to test installation if you want to remain offline.

Before calling the system fully hosted and mobile-accepted, capture:

- Real Vercel URL and production login/journal checks.
- Persistent Railway data surviving restart and a backup/restore check.
- Chosen services' measured monthly resource projection.
- An iPhone run with pinch, pan, crosshair and signal long-press evidence.
- Chart p95 interaction measurement with 2,000 displayed bars; target below 100 ms.
- Signed build/TestFlight evidence when you supply those accounts.
- Notification reception and deep-link behavior when you enable delivery.
- Any optional provider's entitlement, timestamp and license evidence before its data is treated as available.

Implementation and tests may be complete while these external acceptance items remain pending. Consult [PROGRESS.md](PROGRESS.md), [DEBT.md](DEBT.md), [LICENSE-AUDIT.md](LICENSE-AUDIT.md) and the wave reviews for the latest recorded evidence.

## Web passkeys on Render

The user's backend is hosted on **Render**; Railway instructions elsewhere are an alternative, not an additional required service. The confirmed web origin is `https://selery-web.vercel.app`. This update does not provision or modify either hosted service.

Set these values on the existing Render API service:

| Variable/resource | Required value or action |
| --- | --- |
| `SELERY_PASSKEY_ORIGIN` | `https://selery-web.vercel.app` — the web origin, not the Render backend URL; no path |
| `SELERY_PASSWORD` | Keep your existing private password for first enrollment and recovery |
| `SELERY_SESSION_SECRET` | Keep the existing strong backend session secret |
| `SELERY_ALLOWED_ORIGINS` | Include `https://selery-web.vercel.app` |
| Persistent database | Preserve the existing database. If using SQLite at `/app/data/selery.db`, keep the writable persistent disk mounted at `/app/data` and `SELERY_DATABASE_URL=sqlite:////app/data/selery.db` |
| API instances | One process/instance; pending challenges and attempt limits are currently held in process memory |

Deploy the updated backend and web. Vercel's server-only `SELERY_API_URL` must still point to your Render HTTPS API origin. The backend installs `webauthn` from `uv.lock`; startup creates the `auth_credentials` table through the existing schema initialization. Migration `004_passkeys.sql` also records the table for managed migration workflows. Public keys live in the persistent backend database; losing that database requires enrollment again. Include it in existing backup/restore checks.

Sign in once with the workspace password, open **Settings → Touch ID & passkeys**, confirm the password and enable the passkey. Sign out and test **Open workspace**. Also test cancellation and password recovery on your Mac. No Google account, email service, biometric API key, or separate passkey subscription is required. A domain change needs backend origin reconfiguration and enrollment for the new domain.

For local development use `SELERY_PASSKEY_ORIGIN=http://localhost:3000`, with that exact browser URL. Keep it separate from the production Render setting. WebAuthn binds credentials to a domain and verifies the calling origin; direct IP addresses are unsuitable. [WebAuthn specification](https://www.w3.org/TR/webauthn-3/)

The browser test uses a virtual authenticator. It does not prove hosted deployment, a physical Touch ID prompt, or database persistence on Render. See [web passkey review](reviews/web-passkeys.md).

## Final local verification notes

The optional ML dependency group was installed and exercised locally, including Torch 2.14.0, LightGBM 4.7.0, SHAP 0.52.0 and Numba 0.67.0. The lock explicitly constrains modern Numba to avoid an unsupported Python 3.12 resolution. On macOS, LightGBM also needs `brew install libomp`; Linux model images need an OpenMP runtime such as `libgomp1`. Sequence CPU training uses one thread, with a regression covering its interaction with indicator initialization. No successful real-market model is implied by architecture tests.

See [operations and recovery](docs/OPERATIONS.md), [measured fixture resources](docs/runtime-profile.json), [verification](reviews/verification.md) and the [requirement-by-requirement coverage](docs/REQUIREMENT-COVERAGE.md). The full scope is not yet accepted; that matrix distinguishes missing code from missing external evidence.
