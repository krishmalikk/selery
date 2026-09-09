You are a senior full-stack engineer and quantitative developer. Build me a
personal trading research platform called SELERY, delivered as TWO surfaces:

  1. A WEB APP I use on my desktop — the full research environment
  2. A NATIVE MOBILE APP I use on my phone — the check-in and react surface

Both are first-class. Neither is a fallback for the other. They share one
backend, one strategy engine, and one set of types.

SELERY is a RESEARCH AND PAPER-TRADING tool, not an auto-executing money
manager. Treat that as a hard requirement, not a suggestion.

SELERY is a SINGLE-USER PERSONAL tool. Not commercial, not multi-tenant, not
distributed to anyone else. No user_id on every table, no org/team model, no
billing, no enterprise auth posture. One user, one account, two devices.

===============================================================================
PART 0 — CREDENTIALS: ALREADY PRESENT, DO NOT ASK FOR THEM
===============================================================================
My Alpaca API key, secret and base endpoint URL are ALREADY in the .env file at
the repo root. Before writing any data-layer code:
1. Read .env and use the EXACT variable names already there. Do not invent new
   names, do not rename them, do not ask me to re-enter them.
2. Write .env.example mirroring those names with placeholder values.
3. Confirm .env is in .gitignore. If not, add it immediately and check git
   history for any prior commit of it.
4. Determine from the endpoint URL whether it points at paper trading
   (paper-api.alpaca.markets) or live (api.alpaca.markets). If it points at
   LIVE, STOP and tell me before making a single authenticated call.
5. Verify with one read-only call (account info) and paste the result before
   building anything on top of it.
Never log, print, echo or commit the key or secret. Credentials live ONLY on the
server. The mobile app and the web client both call my own API — neither ever
holds an Alpaca or LLM key. Tell me which other keys you need (Finnhub, LLM
provider) and I will add them to .env.

===============================================================================
PART 1 — THE TWO SURFACES
===============================================================================

--- WEB APP (desktop-first, apps/web) ---
This is where I do the actual work. Optimize for a large screen and a keyboard.
- Multi-pane resizable layout: chart + signal list + news + positions
  simultaneously. Saved layout presets.
- Command palette (Cmd-K): jump to ticker, run backtest, toggle strategy,
  open a view. Ticker hotkeys. Everything reachable without a mouse.
- The research surfaces that only make sense big: backtest results and
  tearsheets, the walk-forward validation views, the strategy comparison
  matrix, the alpha101 IC-decay table, the multi-agent debate transcript, the
  feature-store and SHAP explorer, the trade journal with chart snapshots.
- Dense information display. Multiple charts at once. Deep-linkable URLs for
  every view so I can bookmark a specific backtest.
- Responsive down to tablet, but do NOT compromise the desktop layout to make
  it work on a phone. Phones get the native app.

--- MOBILE APP (native, apps/mobile, React Native + Expo) ---
This is where I check in, not where I research. Optimize for thumbs, glances,
and being away from my desk.
- Watchlist with live quotes, sparklines, and today's signals
- Full chart with signal markers — touch-native: pinch to zoom, drag to pan,
  long-press a marker for its detail sheet. Chart quality here is not
  negotiable; it is the main reason I open the app.
- Alerts inbox with push notifications (signal fired, level crossed, risk
  limit breached, watchlist news)
- News feed, filtered to the watchlist
- AI chat, including a one-tap "explain this move" on any chart
- Positions view and trade-ticket approval (paper) — review and confirm a
  ticket the system proposed, never compose a complex order from scratch
- Explicitly NOT on mobile: running backtests, the model explorer, layout
  editing, strategy parameter tuning. Where relevant, show a "open on desktop"
  affordance instead of a cramped version.
- Offline-tolerant: cache last-known state and render it with a staleness
  indicator rather than a spinner or an error.
- Deep links from push notifications straight to the relevant chart and marker.

--- WHAT THEY SHARE (packages/shared — treat as load-bearing) ---
All of this is written ONCE and imported by both surfaces:
- Every TypeScript type and API response schema
- The typed API client
- Strategy signal logic that runs client-side, indicator math, all formatting
  (prices, percentages, timestamps, timezones)
- Design tokens: color, type scale, spacing. One visual identity across both.
- Validation and risk-rule evaluation
Rule: if a piece of logic exists in both apps, it belongs in packages/shared.
The self-review explicitly checks for duplicated logic between web and mobile.

--- DISTRIBUTION ---
- Web: Vercel Hobby (free, personal non-commercial use)
- Mobile: Expo Go during development, then EAS Build → TestFlight for iOS.
  This requires an Apple Developer account at $99/year — flag it when you reach
  that step so I can sign up. Give me the exact eas.json config and the command
  sequence. Android via EAS internal distribution ($25 one-time, optional).
- Also ship the web app as an installable PWA (manifest, icons, standalone
  display) as a convenience, but the native app is the real mobile surface.

===============================================================================
PART 2 — EXECUTION MODEL: WAVE-PARALLEL
===============================================================================
Do not run phases linearly. Group into waves; within a wave, dispatch
independent tracks in parallel using subagents in separate git worktrees.

--- WAVE 0 (serial, blocking) — CONTRACTS AND FIXTURES ---
Emit as CODE, not prose:
- The .env audit above, completed and reported
- packages/shared in full: MarketDataProvider interface, Strategy base class,
  every API route type, DB schema and migrations, shared enums, design tokens,
  the typed API client. Both apps are built against this from their first line.
- THE COST MODEL, fully implemented, not stubbed: commission, SEC/TAF fees,
  bid-ask spread, slippage, short borrow, market impact. Pure functions with
  unit tests against hand-computed cases. Every strategy in every later wave
  imports this. No strategy is ever evaluated frictionless except in the
  explicit before/after comparison.
- packages/fixtures: recorded OHLCV (SPY/QQQ at 1m, 5m, 1D), sample news
  payloads, a sample options chain. Every later track develops against
  fixtures, never a live API. Tests are deterministic and offline.
- A charting decision, written up in DECISIONS.md: TradingView Lightweight
  Charts on web; for mobile, evaluate Lightweight Charts in a WebView versus a
  native RN charting library, and pick based on touch quality and marker
  rendering. Whichever you pick, the marker data contract is identical on both.
- CLAUDE.md with the project non-negotiables
- LICENSE AUDIT of every repo in Part 5
Nothing proceeds until Wave 0 is complete and reviewed.

--- WAVE 1 (serial, blocking) — BOTH SURFACES, THIN SLICE ---
Prove the vertical slice on BOTH platforms before building anything wide.
Shared: watchlist (SPY, QQQ, AAPL, NVDA), live quotes via Alpaca, candlestick
chart at 5m/1h/1D, EMA(9/21) + RSI(14) + VWAP, ONE strategy (EMA 9/21
crossover) rendered as tappable buy/sell markers, news feed from Alpaca.
- apps/web: desktop layout, deployed to Vercel, verified in a browser
- apps/mobile: same data, running on my phone through Expo Go, verified with a
  real device screenshot
- Both consume packages/shared. Zero duplicated logic between them.
- A visible "IEX only" badge on quotes on BOTH surfaces so I never mistake IEX
  volume for consolidated market volume
Deliver: file tree, full code, `npx vercel --prod` steps, and the exact
`npx expo start` + Expo Go steps to get it on my phone today.

--- WAVE 2 (8 parallel tracks, one git worktree each) ---
  A: data layer, TimescaleDB, all provider adapters
  B: web charting — full indicator set, market-structure overlays (fixtures)
  C: news + sentiment pipeline
  D: ETF/SPY domain module
  E: risk engine, alerts, trade journal
  F: strategies 1-7, written against the Wave 0 cost model
  G: strategies 8-13 plus the alpha101 feature layer
  H: mobile app — navigation, watchlist, touch charting, alerts inbox,
     push notification plumbing, offline cache
Rules: own branch, own tests, no cross-track imports outside packages/shared.
If two tracks need to change the same shared file, NEITHER does — log it in
DECISIONS.md and resolve at the wave boundary.

--- WAVE 3 (serial, needs A + F + G) — BACKTEST ENGINE ---
Orchestration engine, portfolio state, walk-forward driver, metrics, honesty
guardrails. Run every Wave 2 strategy through it and produce, for each: the
frictionless-vs-costed comparison, the SPY buy-and-hold benchmark, the deflated
Sharpe and overfitting-risk score, the regime breakdown, and the crowding check.
Backtest UI is web-only.

--- WAVE 4 (serial, needs Wave 3) — ML ---
Feature store, ML/DL agent, walk-forward validation, meta-labeling ensemble.
Model explorer and SHAP views are web-only; mobile shows the resulting
confidence score on a marker and nothing more.

--- WAVE 5 (parallel) ---
  AI chat assistant (both surfaces) | EAS Build + TestFlight setup |
  CI, monitoring, docs

--- SELF-REVIEW PROTOCOL ---
Within a wave, per track: 3-line check — does it run, do tests pass, any
lookahead risk in new signal code.
At each wave boundary: the full review below, written to /reviews/wave-N.md,
plus an integration test exercising the tracks together. Be adversarial with
your own work. Assume you cut a corner somewhere and find it.
1. SPEC COMPLIANCE — list each requirement, mark DONE / PARTIAL / SKIPPED.
   Nothing silently disappears. PARTIAL and SKIPPED go on the debt list.
2. DOES IT ACTUALLY RUN — install clean, run it, paste real terminal output.
   From Wave 1 on, this means BOTH surfaces: the web build and the mobile
   bundle. "This should work" is not evidence.
3. TESTS — do they exist, pass, and test behavior rather than restating the
   implementation? Paste run output and coverage.
4. THE LOOKAHEAD AUDIT (Wave 2 onward, the most important review item in this
   project) — for every new piece of signal or feature code, trace where each
   input value comes from and confirm it was knowable at that bar's timestamp.
   Look specifically for: indicators computed on the full series then sliced,
   forward-filled data, labels leaking into features, resampling that pulls a
   bar's own close into an earlier bar, and normalization fit on the whole
   dataset. State explicitly what you checked.
5. SHARED-CODE AUDIT — list any logic that now exists in both apps/web and
   apps/mobile. Anything on that list is a defect; move it to packages/shared
   before the wave passes.
6. SECURITY — no key in any client bundle (web OR mobile), no secret in git
   history, all external calls server-side. Grep and paste the result.
7. HONESTY CHECK — did anything here produce a number that flatters the system?
   For each, name the assumption that makes it optimistic and whether it's
   disclosed in the UI.
8. WHAT I'D DO DIFFERENTLY — one paragraph, as if reviewing someone else's PR.
   If you can't find a real criticism, you didn't look hard enough.
9. VERDICT — PASS or FAIL. FAIL means fix it now, re-review, then proceed.
   Never proceed on a FAIL. Never grade generously to keep moving.

--- RUNNING RECORD ---
Update at every wave boundary: PROGRESS.md, DECISIONS.md (every judgment call,
reasoning, what you rejected), DEBT.md (every PARTIAL or SKIPPED item, why,
cost to fix later). At the end write FINAL-REVIEW.md: honest overall assessment,
top five weaknesses in Selery as built, what you'd fix first.

--- WHEN TO STOP AND ASK ---
Only for: a credential or paid account I must create myself (the Apple
Developer account is one), a genuine architectural fork that would be expensive
to undo, or a wave that fails its review twice. Otherwise keep going. Small
uncertainties: make the call, log it in DECISIONS.md, move on. Do not ask for
approval between waves.

===============================================================================
PART 3 — COST DISCIPLINE
===============================================================================
- Budget: ~$5/month server (Railway hobby or Fly.io pay-as-you-go) plus Vercel
  Hobby for web. Apple Developer $99/year when we reach TestFlight. Do not
  introduce any other paid service without telling me first and stating cost.
- Free data tiers only: Alpaca (paper + IEX real-time + news), Finnhub, Alpha
  Vantage / Twelve Data, yfinance, FRED, SEC EDGAR, Kenneth French. Build the
  paid adapters (Polygon/Massive, Databento, Alpaca SIP) behind the provider
  interface but leave them unconfigured.
- LLM API calls are the largest recurring cost and the only one that can run
  away. Implement a hard monthly spend cap with a kill switch, log token spend
  per feature, surface it in web settings, and default the multi-agent debate
  to manual-trigger only — never on a schedule. Route cheap tasks
  (summarization, tagging, dedupe) to a small model.
- Prefer pandas-ta over TA-Lib as the default indicator library; TA-Lib needs a
  C build and is a recurring install failure. Keep it optional.
- Both apps are clients. The backtester, model training, ingestion and
  retraining run on the server. Never bundle the ML layer into either app.

===============================================================================
PART 4 — STACK AND DATA LAYER
===============================================================================
Repo: selery. Monorepo (Turborepo): apps/web, apps/mobile, apps/api,
packages/shared, packages/strategies, packages/fixtures, packages/ui.
- Web: Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui
- Mobile: React Native + Expo (managed workflow), Expo Router, Expo
  Notifications for push, MMKV or AsyncStorage for the offline cache
- Backend: Python FastAPI for anything quant/ML; Node only for BFF/auth
- DB: Postgres + TimescaleDB for OHLCV; Redis for cache/pubsub
- Queue: Celery or Arq for ingestion, retraining, nightly backtests
- API: one versioned REST/WebSocket surface serving both clients. Design
  endpoints for BOTH — mobile needs smaller, denormalized payloads on cellular;
  don't force it to fetch a desktop-sized response.
- Auth: single user. One env-var credential or Clerk free tier, with a token
  the mobile app stores in Expo SecureStore. Don't over-build.
- Deploy: Docker Compose local, Fly.io/Railway for API, Vercel for web,
  EAS for mobile

Build a `MarketDataProvider` interface so sources swap without touching feature
code. Adapters:
- Alpaca — credentials already in .env. Free real-time IEX equities + paper
  trading + news in one key. The free tier is IEX only, NOT consolidated SIP.
  Never present IEX volume as total market volume on either surface.
- Finnhub — quotes, company news, fundamentals, WebSocket
- Alpha Vantage and/or Twelve Data — fallback; free tiers are 15-min delayed
- yfinance — free historical bulk backfill
- Polygon.io (now Massive), Databento — built but unconfigured
- FRED — rates, CPI, unemployment, yield curve
- SEC EDGAR full-text search; CBOE for VIX; SSGA for SPY holdings/distributions
- Kenneth French Data Library — factor returns for the factor strategies
Cache aggressively, respect rate limits, auto-backfill gaps, archive raw
responses so ingestion replays deterministically.

===============================================================================
PART 5 — THE GITHUB REPOSITORIES TO PORT FROM
===============================================================================
These are the source repos for Selery's strategy engine. Clone or read each,
extract the logic and architectural pattern, and reimplement cleanly with a
source citation in the code comments. Do NOT vendor-dump or copy whole files.
Verify every license in Wave 0 before writing a line.

>>> TIER 1 — STRATEGY SOURCE MATERIAL (port the actual trading logic) <

1. https://github.com/je-suis-tm/quant-trading
   ~10.7k stars, 1.9k forks, Apache-2.0. THE primary source for Selery.
   Port: MACD oscillator, pair trading via Engle-Granger cointegration,
   Heikin-Ashi, London Breakout (adapt to the US cash open), Awesome Oscillator
   saucer, Dual Thrust, Parabolic SAR, Bollinger Bands pattern recognition
   (double bottom / top M / head-and-shoulders), RSI pattern recognition,
   options straddle, VIX calculator.
   CRITICAL: the author states these backtests assume frictionless trading — no
   slippage, no fees, no illiquidity. Every ported strategy runs through the
   Wave 0 cost model and you show me before/after side by side.

2. https://github.com/yli188/WorldQuant_alpha101_code
   ~859 stars, 252 forks. The 101 Formulaic Alphas (Kakushadze 2016).
   Also: https://github.com/lvlh2/alpha101 — cleaner, pip-installable
   (`pip install alpha101`). Input is a DataFrame MultiIndexed on
   [symbol, date] with open/high/low/close/volume/market_value/return/vwap/
   industry. It skips binary-valued alphas (e.g. Alpha#21) that don't survive
   standard portfolio-sort analysis — do the same.
   Implement as FEATURES for the ML layer, never as standalone strategies.
   Assume they are crowded and decayed; measure each one's IC decay over time
   and show me which are still alive.

3. https://github.com/iterativv/NostalgiaForInfinity
   ~3.3k stars, 742 forks, 14,000+ commits. Crypto only — do NOT port the
   signals. DO port the architecture: a large library of numbered,
   independently-testable entry conditions, each with its own exit logic and
   its own attribution in the trade log.

>>> TIER 2 — ENGINES AND FRAMEWORKS (port the architecture) <

4.  https://github.com/QuantConnect/Lean          (~18k stars, Apache-2.0)
    Algorithm lifecycle, data slices, universe selection.
5.  https://github.com/microsoft/qlib             (MIT)
    Point-in-time data infrastructure, alpha expression language,
    config-driven orchestration, model zoo. Steal the data-correctness design
    above everything else in this list.
6.  https://github.com/nautechsystems/nautilus_trader
    Event-driven backtest/live parity.
7.  https://github.com/polakowo/vectorbt
    Vectorized fast parameter sweeps.
8.  https://github.com/kernc/backtesting.py
    The minimal Strategy / init() / next() interface. Use this shape for
    Selery's Strategy base class.
9.  https://github.com/freqtrade/freqtrade        (GPL-3.0 — check before copying)
    Strategy interface, hyperopt, ROI/stoploss config design.
10. https://github.com/StockSharp/StockSharp      (~9.4k stars, Apache-2.0)
    Connector abstraction, order management, production architecture.

>>> TIER 3 — MACHINE LEARNING <

11. https://github.com/baobach/mlfinpy            (MIT)
    The de Prado toolkit: triple-barrier labeling, meta-labeling, fractional
    differentiation, purged and embargoed K-fold CV. Implement this methodology
    BEFORE any model. Naive next-day-return labels and standard K-fold are
    FORBIDDEN in this codebase. If mlfinpy is missing a piece, implement it
    from the published de Prado method with our own tests.
    DO NOT USE https://github.com/hudson-and-thames/mlfinlab — licensed
    all-rights-reserved, explicitly NOT open source, requires a purchased
    commercial license, terms changeable unilaterally. mlfinpy exists
    precisely because of this.
12. https://github.com/stefan-jansen/machine-learning-for-trading
    End-to-end pipeline: data sourcing → alpha factor research → execution.
13. https://github.com/AI4Finance-Foundation/FinRL
    Deep reinforcement learning environments for finance. Optional.
14. https://github.com/huseinzol05/Stock-Prediction-Models
    ~9.3k stars. REFERENCE ONLY. LSTM/GRU/encoder-decoder forecasters plus
    Q-learning and evolution-strategy agents. Roughly two years stale and its
    headline results are in-sample. Read for architectures; ignore its claims.
15. https://github.com/pskrunner14/trading-bot     (~1.1k stars)
    Compact deep Q-learning reference implementation.

>>> TIER 4 — LLM AGENTS <

16. https://github.com/TauricResearch/TradingAgents
    Multi-agent firm simulation: fundamental, sentiment and technical analysts
    feed a trader, then a risk management team, with structured bull/bear
    debate. Multi-provider LLM support. The authors are explicit that it is
    research software and not investment advice.
17. https://github.com/virattt/ai-hedge-fund
    Analyst personas propose, technicals agent generates signals, risk manager
    sets position limits, portfolio manager makes the final call. Simulates
    decisions; does not trade.
18. https://github.com/LLMQuant/awesome-trading-agents
19. https://github.com/georgezouq/awesome-ai-in-finance
    Curated indexes — pull additional current projects from these at build time.

>>> TIER 5 — INDICATORS, ANALYTICS, CURATED LISTS <

20. https://github.com/twopirllc/pandas-ta        — DEFAULT indicator library
21. https://github.com/TA-Lib/ta-lib-python       — optional; needs a C build
22. https://github.com/ranaroussi/quantstats      — tearsheets, Sharpe/Sortino/
                                                    Calmar, drawdown analysis
23. https://github.com/robertmartin8/PyPortfolioOpt — sizing, efficient
                                                      frontier, HRP
24. https://github.com/ranaroussi/yfinance        — free historical backfill
25. https://github.com/tradingview/lightweight-charts — charting, both surfaces
26. https://github.com/paperswithbacktest/awesome-systematic-trading
    Ranked index of 136+ libraries.
27. https://github.com/leoncuhk/awesome-quant-ai
    Factor definitions and academic references (Gatev/Goetzmann/Rouwenhorst on
    pairs trading, Avellaneda & Lee on statistical arbitrage, Harvey/Liu/Zhu on
    the factor zoo).

>>> STRATEGIES TO SHIP (each independently backtested, individually toggleable) <
1.  EMA/SMA crossover baseline — the control group; everything must beat it
2.  MACD oscillator
3.  RSI mean reversion with regime filter (only when ADX is low)
4.  Bollinger Band fade + Bollinger pattern recognition
5.  Dual Thrust / opening range breakout on SPY
6.  Parabolic SAR trend following with ATR trailing stop
7.  Heikin-Ashi momentum
8.  Pairs trading via Engle-Granger cointegration (SPY/QQQ, sector pairs).
    Re-test cointegration continuously — the relationship decays, and trading a
    broken pair is the classic way this strategy blows up.
9.  Cross-sectional 12-1 momentum, monthly rebalance
10. Fama-French factor tilts (value, momentum, size, quality, low-vol)
11. Post-earnings-announcement drift
12. Volatility regime gate — VIX term structure and IV rank gating all the above
13. Seasonality — day-of-week, turn-of-month, pre/post-FOMC drift
14. ML meta-labeling ensemble deciding WHICH of 1-13 to actually take. Per de
    Prado, the meta-model's job is filtering and sizing, not direction. This is
    the highest-value component in Selery.

===============================================================================
PART 6 — CHARTS AND SIGNAL MARKERS (the centerpiece, on both surfaces)
===============================================================================
- Timeframes: 1m, 5m, 15m, 1h, 4h, 1D, 1W
- Indicators: EMA/SMA ribbons, VWAP + anchored VWAP, RSI, MACD, Bollinger, ATR,
  ADX, OBV, volume profile, Ichimoku, stochastic, Supertrend, Parabolic SAR
- Market structure: support/resistance zones, trendlines, order blocks, fair
  value gaps, prior day/week high-low, opening range, gap fills
- SIGNAL MARKERS: buy/sell/exit arrows at the exact bar the signal fired. On
  web, hover for detail; on mobile, long-press for a bottom sheet. Same data
  either way: which strategy and direction; confidence 0-1 with top SHAP
  features; suggested entry, stop, target and R:R; position size implied by my
  risk settings; historical hit rate of that signal type on that ticker and
  timeframe.
- "Signal replay": scrub bar-by-bar, strictly no lookahead. Web only.
- Correlation / relative strength: SPY vs QQQ, IWM, DIA, sectors (XLK, XLF,
  XLE...), VIX, DXY, TLT, plus breadth internals. Web only.
- News markers overlaid on price, tappable through to source, both surfaces.

===============================================================================
PART 7 — NEWS AND SENTIMENT
===============================================================================
- Ingest continuously: Alpaca News, Finnhub News, RSS, SEC filings, earnings
  calendar, economic calendar (FOMC/CPI/NFP/PCE)
- Dedupe near-identical stories via embedding similarity; cluster into events
- Score each: watchlist relevance, sentiment, novelty, expected impact
- A "why is SPY moving right now" panel tying intraday moves to specific events

===============================================================================
PART 8 — DEEP LEARNING AGENT
===============================================================================
- Feature store: price/volume derived, technicals, the alpha101 set,
  cross-asset, macro, sentiment, options-derived (put/call ratio, skew, gamma
  proxy), calendar. Versioned, point-in-time correctness enforced at storage.
- Labeling: triple-barrier with meta-labeling. Never naive forward returns.
- Models: LightGBM/XGBoost baseline + sequence models (LSTM/GRU/TFT) + optional
  PPO/SAC via FinRL. Always report the baseline next to the complex model.
- Validation: walk-forward with purged, embargoed K-fold. Reject anything not
  stable across folds AND across a final held-out period.
- Explainability: SHAP in the web UI for every prediction.
- Calibration: calibrated probabilities with a reliability diagram.
- Nightly retrain, model registry, drift detection, auto-rollback to champion.

===============================================================================
PART 9 — AI CHAT ASSISTANT (both surfaces)
===============================================================================
- Streaming chat with tool-calling against Selery itself. Tools: get_quote,
  get_chart_data, run_backtest, explain_signal, screen_universe, get_news,
  get_fundamentals, get_portfolio, compute_position_size, get_filings.
- RAG over ingested news, backtest results, trade journal, my notes.
- Multi-agent mode modeled on TradingAgents + ai-hedge-fund: bull analyst, bear
  analyst, technical analyst and risk manager debate a ticker; a portfolio-
  manager agent writes the final memo with an explicit invalidation condition.
  Full debate transcript on web; mobile shows the memo with a link to open the
  transcript on desktop. MANUAL TRIGGER ONLY — the most expensive feature in
  Selery, and it must never run on a schedule.
- Every claim about data must cite the underlying data point and timestamp.
- The assistant must NEVER place an order. It can only prepare a proposed trade
  ticket that I manually confirm.

===============================================================================
PART 10 — ETF / SPY DOMAIN MODULE
===============================================================================
- Holdings, weights, sector breakdown, top-10 concentration, live drift
- NAV vs price premium/discount, creation/redemption mechanics
- Expense ratio, dividend schedule, ex-div dates and the associated price drop
- SPY vs SPX vs ES vs /MES: settlement, hours, Section 1256 tax treatment,
  assignment risk. SPY vs VOO vs IVV: liquidity, spreads, options depth
- Options context: 0DTE dynamics, IV rank/percentile, straddle-implied expected
  move, max pain, gamma exposure proxy — used to gate the signal engine
- Index events: rebalances, quad witching, adds/drops
- Overnight vs intraday return decomposition
- Market internals: ADD, TICK, VOLD, put/call ratio, breadth thrusts

===============================================================================
PART 11 — BACKTESTING AND HONESTY GUARDRAILS (non-negotiable)
===============================================================================
Selery must actively resist fooling me. There is no colleague to catch the
mistake — the guardrails are the only check.
- Point-in-time data only. No lookahead. No survivorship bias in universes.
- Every strategy shown both frictionless (as its source assumed) and after the
  Wave 0 cost model.
- Metrics: Sharpe, Sortino, Calmar, max drawdown, time-under-water, win rate,
  profit factor, expectancy, turnover, CVaR.
- ALWAYS benchmark against buy-and-hold SPY. If a strategy doesn't beat it
  after costs on risk-adjusted terms, say so loudly and prominently in the UI.
- Multiple-testing correction: track how many parameter combos were tried,
  apply a deflated Sharpe ratio, display an overfitting-risk score. This is the
  "factor zoo" problem (Harvey, Liu & Zhu) — most published factors don't
  survive it, and neither will most of mine.
- Monte Carlo trade-order shuffling and bootstrapped equity curves with
  confidence intervals. Never a single hopeful line.
- Regime breakdown: 2008, 2018 Q4, 2020 crash, 2022 bear, 2023-25 bull.
- CROWDING CHECK: for every strategy ported from a public repo, plot
  performance before vs after that repo's publication date. Show me the decay.

===============================================================================
PART 12 — RISK, PAPER TRADING, ALERTS
===============================================================================
- Configurable max risk per trade, max daily loss, max open positions, max
  sector/correlation exposure, max drawdown kill-switch
- Sizing: fixed-fractional, ATR-based, capped Kelly fraction
- Pre-trade check blocking any ticket that violates my rules, enforced
  server-side so both clients get the same answer
- Correlation-aware exposure: warn when five "different" positions are one bet
- Alpaca paper trading wired end to end using the .env credentials
- Live order routing behind a feature flag, OFF by default, requiring separate
  explicit confirmation, with hard caps. Not exposed on mobile at all.
- Full audit log of every signal, decision and paper fill
- Trade journal: notes + auto-attached chart snapshot, thesis, outcome, and a
  "right for the right reason?" post-mortem field. Quick-capture on mobile,
  full editing on web.
- Alerts: push (Expo Notifications), email, Discord/Telegram. Types: signal
  fired, level crossed, unusual volume, watchlist news, IV spike, model
  confidence threshold, risk limit breached. Deduped and rate-limited. Push
  notifications deep-link into the relevant chart and marker.

===============================================================================
PART 13 — DESIGN AND TONE
===============================================================================
- Selery's identity: dark-first, dense, precise. Not neon crypto-bro, not
  sterile enterprise. Propose a small palette and one typeface pairing in
  Wave 0, put it in packages/shared as tokens, and hold it across both
  surfaces. Selery should be recognizably itself on desktop and phone.
- Web: keyboard-driven, command palette, dense multi-pane.
  Mobile: thumb-driven, one thing at a time, large touch targets.
  Both: sub-100ms chart interaction, WebSocket live updates.
- Be blunt about what won't work. Every Tier 1 strategy has been public for
  years and is therefore crowded — build them, but tell me when the evidence
  says one is dead. If a feature I asked for is a known way retail traders lose
  money, build it and flag the risk in the UI.
- Persistent disclaimer on both surfaces: Selery is research software, not
  investment advice, and backtested performance does not predict live results.

===============================================================================
BEGIN AT WAVE 0, STARTING WITH THE .ENV AUDIT. RUN STRAIGHT THROUGH TO WAVE 5,
SELF-REVIEWING AT EVERY WAVE BOUNDARY. DO NOT ASK FOR APPROVAL BETWEEN WAVES.
===============================================================================