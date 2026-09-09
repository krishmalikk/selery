# SELERY web guide

The desktop app is a personal research workspace for prices, signals, historical event studies and source context. It shares a Python backend with the native app. This guide describes implemented behavior and identifies resources or acceptance still pending.

**Selery is research software that displays analysis. It does not execute, recommend, or place trades.**

For all credentials, account setup and costs, start with [SETUP-REQUIREMENTS.md](SETUP-REQUIREMENTS.md). For native usage, see [MOBILE-GUIDE.md](MOBILE-GUIDE.md).

## 1. Start and sign in

From the repository root, after reviewing your existing `.env`:

```sh
uv sync --frozen --group dev
npm ci
```

Keep the API running in one terminal:

```sh
PYTHONPATH=apps/api:packages/shared/python:packages/strategies/python uv run uvicorn selery_api.main:app --host 127.0.0.1 --port 8000
```

Start the web app in another:

```sh
npm run dev
```

Open `http://localhost:3000`. Enter the backend's `SELERY_PASSWORD`, not an Alpaca credential. The web app proxies requests through its own server and keeps the session in an HttpOnly cookie. Sessions last one hour. A password is not saved in browser storage; the browser login response does not expose the backend bearer token.

Use **Sign out** to revoke the session and clear cached research/layout data. Rotating `SELERY_SESSION_SECRET` on the backend invalidates signed sessions. This is one personal login, not a multi-user tenant system.

## 2. Workspace map

| Page | What it does |
| --- | --- |
| Overview | Watchlist cards, chart, backend indicators, signal details, comparison chart and news |
| Research | Runs an explicit historical signal-event study and displays report metrics, assumptions, limitations and export |
| Outcomes | Shows matured forward signal observations grouped by matching research settings |
| Journal | Saves your own thesis, observed outcome and reflection only when you choose Save entry |
| Sizing | Calculates informational research size from your own risk/capital/reference inputs |
| Alerts | Lists backend research alerts, opens a symbol and marks an alert read |
| Assistant | Local source-linked data summary or optional funded LLM research response |
| Settings | Data mode/feed, LLM state and cap, SPY data availability, model/validation metadata |

The navigation can collapse to leave more chart space. The layout adapts to smaller screens, while the native app provides the phone-oriented experience. The palette uses charcoal surfaces, sage for positive/context accents, amber for limitations, and muted red for negative observations. Local Inter and JetBrains Mono font assets avoid a build-time font service dependency.

## 3. Overview: quotes, charts and evidence

### Watchlist

The initial research universe is SPY, QQQ, AAPL and NVDA. Selecting a card changes the active symbol. Each quote displays its feed and source/freshness context. Recorded daily bars provide fixture reference quotes; they are not live last-sale claims.

- **IEX only** means venue-limited data. It is not a consolidated market quote or NBBO.
- **Fixture data** means the API is serving recorded data. Recordings can be genuine provider observations while still stale today.
- **Synthetic fixture** explicitly identifies generated test data, where present. Synthetic test cases are not evidence of live market behavior.
- A stale/offline label means the current display is last-known data and needs a successful refresh before being treated as current.

### Chart controls

The chart defaults to **5m**, with **1h** and **1D** selectors. It renders provider candles and indicator series computed in Python. Mouse drag pans; wheel/axis interaction zooms. The crosshair inspects a time/price point. Oscillator pane separators can be dragged to adjust their height.

Backend-series controls include EMA 9/21, RSI 14, SMA 50, Bollinger bands, MACD, ATR 14 and entitled VWAP. Missing warm-up values remain gaps/unavailable rather than zeros. Indicators are drawn only if the response supplies the relevant series.

**VWAP and other consolidated-volume features are disabled on IEX with “needs SIP data.”** This is enforced by the backend, not just a visual control. Do not infer consolidated volume or a fixed IEX market share from the displayed volume.

Layout presets:

- **Price & trend** selects the trend-focused series.
- **Momentum** selects momentum-focused series.
- **Volatility** selects volatility-focused series.
- **Save layout** stores your current indicator selection locally in the browser.
- **My saved layout** restores that saved selection. It is not synchronized to the phone and is removed on sign out.

**Compare SPY/QQQ** loads a real second chart response with its own feed and timestamp. Its price scale is independent; it is not a normalized relative-return plot. Backend refreshes update the shared chart instance while preserving the visible range and pane heights when its structure is unchanged.

### Replay

Drag the Replay slider to restrict displayed history. Markers appear only when both the signal's event time and recorded availability are inside the visible replay cutoff. **Return to latest** restores the full available response. Replay is observation review; it does not create an account or manufacture outcomes.

The replay slider operates on the fetched chart window. It is not an unlimited historical archive browser. Durable as-of data replay also exists as a backend service for explicitly archived datasets.

### Signal context

Select a chart marker, hover its marker, or activate a row in Recent signals. The detail panel shows:

- Symbol, strategy/version and direction of the analytical observation.
- Reference price and analytical stop/target levels.
- Research horizon in bars and source/feed.
- Event and availability timestamps.
- Signal-time input features and explanation.
- Calibrated confidence only if available; otherwise an explicit reason.

Levels are research thresholds. They do not describe submitted actions or future certainty. Signals use finalized bars; chart responses may still include a latest unfinished candle for visual context. Default overview markers are the EMA crossover research control. Selecting another research strategy is done on the Research page.

### Headlines

Headlines link to source articles. The backend cleans text, removes tracking-link duplicates, clusters sufficiently similar text and provides an explicit lexical sentiment score. The score is a transparent text heuristic, not a trained return predictor. Timing alone does not establish why a price moved.

The richer news pipeline also produces source clusters, relevance, novelty and keyword salience as backend data. The overview currently renders headlines, summaries, sources, timestamps, symbols and sentiment, not a full event-analysis dashboard. Optional SEC/Federal Reserve feeds require deliberate backend integration/configuration and never silently substitute for Alpaca news.

## 4. Historical research reports

Choose symbol, timeframe, enabled strategy and horizon, then select **Run event study**. Strategy options unavailable on the configured feed are disabled with their reason. The API evaluates finalized historical observations and stores the report. **Download report JSON** saves the actual report response, including assumptions and limitations.

The price-based strategy library includes EMA/SMA crossover, MACD, RSI/low-ADX research, Bollinger fades and confirmed W/M patterns, opening-range research, a named Dual Thrust opening-window variant, Parabolic SAR and Heikin-Ashi. Defaults and exact variants are described in the backend catalog. No profitability claim follows from an implemented method.

Advanced research families—pairs, cross-sectional momentum, factors, earnings, volatility context and seasonality—need dated, aligned inputs beyond one symbol's candle window. Those remain unavailable through the simple study form until their dependencies are supplied. The alpha catalog reports each supported/unavailable formula; it does not claim complete Alpha101 coverage. See [advanced research notes](docs/tracks/G.md).

### Reading a report

The report separates threshold outcomes from the analytical return study. Its plotted research series is a fixed-reference additive price-change index in percentage units, after the stated analytical allowances. SPY is a same-feed benchmark with aligned timestamps. These are research indices, not realized performance of an account.

Read the assumptions first:

- Signals affect only intervals after their known availability.
- Research horizons and discarded overlaps follow the report's policy.
- Inactive intervals remain represented in the calendar-aligned study.
- Costs use a versioned, effective-dated model with explicit spread, slippage, impact and other allowances.
- SPY full-spread sensitivity uses assumed $0.01, $0.02 and $0.05 cases; they are not observed spreads.
- Raw prices do not establish corporate-action-adjusted total return.
- Missing benchmark timestamps, insufficient history or unverified rate dates leave corresponding metrics unavailable.

Depending on supported data, metrics include interval/event counts, threshold outcome rates, cost sensitivities, drawdown/underwater diagnostics, expectancy, tail statistics, benchmark comparisons, block-bootstrap intervals and descriptive regime cohorts. Annualized measures require adequate daily observations; intraday annualization is not fabricated. A complete multiple-trial registry is required before deflated Sharpe can be reported. The simple UI does not supply that registry, so the metric can remain unavailable even when its calculation method exists.

The web response may take time for a manual study. The normal page request is synchronous; the optional backend `POST /api/v1/jobs/research` route enqueues a manual Arq job when Redis/worker are configured. The page does not automatically use that route. See [Wave 3 methodology](docs/tracks/wave3.md) for exact normalization, overlap and sample rules.

## 5. Forward outcomes

The forward observer records newly available live signals and immutable signal-time inputs. Fixture browsing does not manufacture a forward track record. The observer must remain running to accumulate future evidence; newly starting it does not reconstruct missed historical capture as forward observations.

Outcomes distinguish:

| State | Meaning |
| --- | --- |
| Pending | Horizon has not yet supplied enough observations |
| Target first | Target threshold is observed before the stop threshold |
| Stop first | Stop threshold is observed before the target threshold |
| Neither | Horizon matures without either threshold being established |
| Ambiguous | Available bars cannot determine threshold order, including both levels touched in one bar |
| Incomplete | Missing evidence prevents a complete classification |

The table shows matured counts, threshold counts, ambiguity and denominator disclosure. Historical/forward comparisons require compatible feeds, strategy versions, timeframes and horizons. An empty table can be correct: no forward evidence has matured yet. A SIP historical study is not directly comparable to IEX forward results.

## 6. Journal and sizing

### Manual journal

Enter a symbol, thesis, observed outcome and reflection. Only **Save entry** sends the journal write. Looking at a chart, running research or asking the assistant never creates a journal entry. The database retains saved records; the app fetches them on the Journal page.

The current web form creates entries. The backend also supports explicit updates by ID, but the page does not yet provide a full edit/delete/archive interface. Do not use an automated agent to invent a personal thesis or outcome.

### Informational size

Supply research capital, risk percentage, reference price, analytical stop level and maximum allocation percentage. The backend computes units constrained by both the risk distance and allocation limit, plus notional and analytical risk. A reference equal to its stop is invalid. The app does not read any broker balance to populate these fields.

Changing inputs does not have an external effect. The output is an informational calculation using your assumptions.

## 7. Alerts and assistant

Alerts originate from backend research events. **Mark read** changes the inbox record. **Open symbol** returns to that chart. External push/email/Discord/Telegram delivery requires separate opt-in and credentials; an inbox entry does not imply delivery to a device.

The assistant works in two modes:

| Mode | Behavior |
| --- | --- |
| Local | Summarizes current available symbol bars/signals and links to available news. It openly states that it cannot answer arbitrary questions. No LLM cost. |
| LLM | Optional Anthropic evidence response with supplied citations, shown cost and a server-controlled spending cap. Disabled by default. |

The **Compare research perspectives** option is enabled only with funded LLM configuration. It invokes distinct analytical perspectives and a memo. It is manually triggered and uses more calls. The chat proxy permits up to 285 seconds, but deployed function limits may be lower. Long requests need operational review before repeated use. Generated text is not a verified market fact; follow its citations and check available timestamps.

No assistant response writes to the journal or has execution tools. Settings shows the cap and consumed/reserved allowance. Missing confidence, SHAP or statistical evidence stays unavailable.

## 8. Settings and domain/model availability

Settings is a status view. Sensitive environment values are managed on the backend and are never displayed as provider secrets.

The SPY domain section provides dated source-linked definitions and fund expense context. Current issuer holdings, aligned NAV, OPRA options inputs and point-in-time macro releases require those datasets; the default view reports them unavailable. Calculation helpers for constituent weights, reference NAV premium, IV move proxy and costs exist on the backend. Their existence does not mean a current live source is connected.

The model registry describes training and validation state. Manual training routes and ML primitives are backend features. A model must meet the backend's dataset/validation requirements before confidence or inference is credible; a rendered model metadata section is not evidence that a useful model was trained or promoted. Optional dependencies and sufficiently long datasets are listed in the setup guide. Scheduled retraining is off.

## 9. Keyboard, URL and storage behavior

| Control | Action |
| --- | --- |
| `Cmd+K` on macOS / `Ctrl+K` | Open or close symbol/page search |
| `Escape` | Dismiss search |
| `Enter` on a focused signal row | Open its detail panel |
| Tab/Shift+Tab | Navigate standard controls |
| Navigation toggle | Collapse/restore the sidebar |

The URL retains `symbol` and `view`, for example `/?symbol=QQQ&view=Research`. Opening such a URL still requires authentication. The command palette searches the initial watchlist and known pages.

Last-known quote/chart/news responses and explicitly saved layouts are browser-local. Shared schema/freshness logic validates cached data. Failed refreshes show cached/stale state, and obsolete responses are discarded after symbol/timeframe changes. Successful requests replace the cache. Journals and reports are backend records, not browser-only storage.

The frontend polls every 30 seconds and can use a one-time-ticket authenticated WebSocket when configured. Reconnect uses bounded backoff; malformed stream messages do not become chart data. A disconnected stream does not prove that cached data is current.

The PWA manifest, standalone display metadata and SVG icon are included. Browser installation support, a fully offline shell/service worker, raster Apple icons and cross-browser offline startup acceptance remain pending. Cached research responses alone do not guarantee a fresh offline launch or offline sign-in.

## 10. Architecture and important interfaces

```text
Browser
  → Next.js same-origin /api/v1 proxy
  → FastAPI personal authentication + research services
  → explicit provider data / durable research database

Browser WebSocket
  → backend /api/v1/stream using a short-lived single-use ticket
```

- Next.js 15 App Router, React, TypeScript and Tailwind-backed styles live in `apps/web`.
- `packages/shared` exports generated TypeScript/Zod contracts, API client, tokens, formatting, cache/stream rules and shared chart rendering.
- Canonical models, indicators, strategies, cost mathematics and outcomes live in Python.
- Lightweight Charts is locally bundled and attributed; indicator calculations do not run in JavaScript.
- The Next server strips the bearer token from successful browser login output while forwarding the HttpOnly cookie.
- The backend handles `/health`; authenticated API documentation is available through the backend's OpenAPI schema for development.

Principal API groups:

| Group | Interfaces |
| --- | --- |
| Session | `POST /api/v1/auth/login`, `/auth/logout`, `/auth/stream-ticket` |
| Market/context | `GET /api/v1/watchlist`, `/chart/{symbol}`, `/news`, `/domain/SPY` |
| Research | `GET /api/v1/strategies`, `POST /api/v1/research`, `GET /api/v1/research/{id}`, `POST /api/v1/research/size` |
| Records | `GET /api/v1/outcomes`, `/journal`, `/alerts`, `/jobs`; explicit journal save and alert-read POSTs |
| Metadata | `GET /api/v1/settings`, `/models`, `/providers`, `/features/catalog` |
| Manual operator features | Provider query/model training routes; availability depends on backend configuration and data |
| Assistant | `POST /api/v1/chat` |
| Stream | `/api/v1/stream` with single-use ticket |

Not every backend operator interface has a dedicated web form. Inspect the generated OpenAPI contract rather than assuming that a library function is an exposed route.

## 11. Build, deploy and verify

```sh
npm run typecheck --workspace @selery/web
npm run build --workspace @selery/web
npm run start --workspace @selery/web
```

Run `start` after a production build, with the backend already running. On Vercel select `apps/web`, include shared source outside that directory, install from the root lockfile and configure `SELERY_API_URL`. The setup guide gives the exact deployment sequence.

Verification available in the project includes production compilation, TypeScript checks, browser interaction tests, and isolated renderer/cache/stream tests. The desktop renderer test measured synchronous updates with 2,000 synthetic bars; that is not physical-device end-to-end touch latency. See [chart verification notes](docs/tracks/B.md).

For browser tests with API and web running:

```sh
npx playwright install chromium
npx playwright test
```

The tests cover visible charts/feed limitations, command navigation, a study request and informational sizing. No test result establishes real investment performance. Vercel production, hosted persistence and a fresh browser install still require their own acceptance records.

## 12. Troubleshooting

| Symptom | Check |
| --- | --- |
| Research service unavailable | API `/health`, `SELERY_API_URL`, correct port, backend startup validation and logs |
| Login rejected | Use `SELERY_PASSWORD`, check password/session-secret lengths; repeated failures are rate-limited |
| Browser works but stream reconnects | Public WSS URL, exact browser origin in backend allowlist and same API instance for ticket/stream |
| Only stale fixtures | Backend `SELERY_DATA_MODE`; recordings are deliberately labeled stale |
| No bars for a symbol/timeframe/feed | That recording/source may not cover the request; no synthetic fallback is created |
| VWAP disabled | Expected on IEX; a UI toggle cannot grant SIP entitlement |
| Research metric unavailable | Read assumptions/sample counts, fee-date coverage, benchmark alignment and trial-registry requirements |
| No outcomes yet | Live observer must capture new signals and their future horizon; fixture browsing does not create evidence |
| Saved data disappears after deploy | Persistent database/volume was absent or a different database URL was used |
| LLM cap reached after a timeout | Reservation may be retained because provider billing outcome is unknown; reconcile before retrying |
| Old layout or stale browser data | Use refresh or sign out; sign out clears SELERY browser cache/layout state |
| PWA does not launch offline | Full offline shell acceptance is not complete; metadata/cache is not a service-worker guarantee |

The accepted scope is [IMPLEMENTATION.md](IMPLEMENTATION.md). Quant methodology, source licensing, remaining limitations and review evidence are maintained in [ARCHITECTURE.md](ARCHITECTURE.md), [LICENSE-AUDIT.md](LICENSE-AUDIT.md), [DEBT.md](DEBT.md) and the track/wave review files.

## Final integration additions

The Research screen now includes a paginated saved-study comparison table. It lists ten stored reports per page with symbol, strategy, feed, timeframe, horizon, event count and target-first rate. Selecting a row loads the full report and its assumptions. `GET /api/v1/research?limit=10&offset=0` powers this view. Comparison does not establish that different cohorts are interchangeable.

Forward comparisons now keep symbols separate as well as feed/version/timeframe/horizon. Unexplained weekday gaps disable annualized ratios; an unverified holiday is not assumed away. Incomplete session coverage cannot resolve a later threshold favorably. WebSocket tickets are tied to the originating session, and existing streams recheck expiry/revocation before sending data.

Eligible calibrated confidence is attached only when a new forward signal is captured and is retained in its immutable snapshot. Historical charts can reuse that exact snapshot; they do not apply a model trained later. `GET /api/v1/models/explain/{signal_id}` requests optional SHAP for a stored signal and reports explicit unavailability when the scope, artifact, timestamps or dependencies do not qualify. This endpoint is currently a manual backend workflow, not a complete SHAP visualization screen.

[Requirement coverage](docs/REQUIREMENT-COVERAGE.md) and [final review](FINAL-REVIEW.md) distinguish implemented screens, unfinished advanced integrations and unverified deployments.
