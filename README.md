# SELERY

A personal market research workspace with a desktop Next.js app, native Expo app and shared Python research backend.

**Selery is research software that displays analysis. It does not execute, recommend, or place trades.**

## Start here

- [Setup requirements](SETUP-REQUIREMENTS.md): credentials, local commands, Vercel/Railway/EAS setup, optional data/LLM/notifications and costs.
- [Web guide](WEB-GUIDE.md): desktop screens, chart interactions, historical studies, outcomes, journal and architecture.
- [Mobile guide](MOBILE-GUIDE.md): native screens, Expo Go, local-network setup, signing, TestFlight and device acceptance.
- [Accepted implementation](IMPLEMENTATION.md), [architecture](ARCHITECTURE.md), [license audit](LICENSE-AUDIT.md), [progress](PROGRESS.md), [decisions](DECISIONS.md) and [debt](DEBT.md).

## Local quick start

Keep the existing root `.env`; compare it with `.env.example` without overwriting credentials. The backend requires the HTTPS Alpaca paper host, a personal password of at least 12 characters and a session secret of at least 32 characters. Fixture mode uses recorded datasets. Provider keys belong only on the backend.

From the repository root:

```sh
uv python install 3.12
uv sync --frozen --group dev
npm ci
```

API terminal:

```sh
PYTHONPATH=apps/api:packages/shared/python:packages/strategies/python uv run uvicorn selery_api.main:app --host 127.0.0.1 --port 8000
```

Web terminal:

```sh
npm run dev
```

Open `http://localhost:3000` and use your personal workspace password. To preview on an iPhone, bind the API to `0.0.0.0` and run:

```sh
EXPO_PUBLIC_API_URL=http://YOUR_COMPUTER_LAN_IP:8000 npm run mobile
```

Use a compatible Expo Go or development build. A physical phone cannot use the computer's `localhost` address. See the mobile guide before setting up push or signed builds.

## What's implemented

Both surfaces display feed-labelled watchlists, chart research, source news, alerts and explicit manual journals. Desktop adds indicator/layout controls, replay, comparison, historical research reports, outcomes, sizing and detailed model/domain status. Python owns quantitative formulas; generated contracts, formatting, cache/stream rules and chart rendering are shared.

The backend includes causal price strategies, advanced data-dependent research methods, an honestly scoped alpha feature catalog, historical signal-event evaluation, effective-dated cost allowances, immutable forward observations, optional provider adapters and archival replay, news deduplication/lexical scoring, SPY context calculations, manual ML facilities and default-off bounded LLM/notification integrations.

Capabilities are conditional on data and validation. IEX volume-dependent features fail closed with **“needs SIP data.”** Missing confidence, histories, entitlements and statistics stay unavailable. Existing holdings context describes ETF constituents, never a user's broker account.

Recorded credential verification and live market-data smoke evidence are in [docs/alpaca-verification.json](docs/alpaca-verification.json) and [docs/live-smoke.json](docs/live-smoke.json). Local compilation/bundling does not establish cloud deployment, real-device acceptance, a useful trained model or paid data access. Read the current review/debt records for those boundaries.

## Repository map

```text
apps/web/                 Next.js desktop application and same-origin API proxy
apps/mobile/              Expo Router native application and local WebView chart bundle
apps/api/selery_api/       FastAPI, auth, providers, research, outcomes, ML and integrations
packages/shared/src/      Generated TypeScript/Zod contracts, client, tokens, chart/cache/stream helpers
packages/shared/python/   Canonical Pydantic models and quantitative primitives
packages/shared/migrations/  Initial database schema
packages/strategies/python/  Independent Python strategy and feature implementations
packages/fixtures/        Source-labelled recorded/test datasets
scripts/                  Contract generation, secret-safe scans and explicit live verification
tests/                    Offline Python/TypeScript and browser checks
docs/tracks/              Track decisions, methodology and validation evidence
Dockerfile                Python API container
compose.yaml              Local TimescaleDB, Redis, API and Arq worker
railway.toml              API deployment configuration
```

## Verify

```sh
npm run typecheck
npm run build
npm run export --workspace @selery/mobile
uv run pytest
npm run test:security
npm run contracts
git diff --exit-code -- packages/shared
```

With API/web running, install Playwright Chromium and run `npx playwright test` for browser checks. Live-provider scripts are separate and may refresh recorded evidence; deterministic tests do not need live credentials.

The approximately $5/month hosting goal is not a guarantee for the complete multi-service stack. Start locally or with one measured persistent API service, keep expensive jobs manual, and configure accounts/limits before enabling paid resources. LLM spending defaults to $0 and external alert delivery defaults off.
