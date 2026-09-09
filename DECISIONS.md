# Decisions

1. The final user correction removes all execution and broker-state capabilities. Python owns all quantitative calculations. Both clients share generated contracts and chart rendering; they never compute strategies.
2. Alpaca credentials retain ALPACA_ENDPOINT, ALPACA_KEY, ALPACA_SECRET. A strict HTTPS paper-host check precedes market-data requests. No account request was made. Read-only historical IEX/SIP and news requests succeeded; evidence is in docs/alpaca-verification.json.
3. Fixture mode is the local default for deterministic development. Fixtures are real recorded data and labeled stale; the options fixture is explicitly synthetic. Live mode is an explicit environment setting, never a silent fallback.
4. SQLite is supported for a zero-service local start. PostgreSQL/TimescaleDB migrations and Compose are the target durable deployment. Redis/Arq is required for the separate job worker, not the local thin slice.
5. A single Python API process owns local sessions/stream tickets and the forward observer. Horizontal replicas require shared auth/observer leadership before deployment. Default server scale is one.
6. Shared WebView/desktop chart renderer uses Lightweight Charts with required attribution. No external chart CDN or key enters mobile. iPhone gesture/performance acceptance remains external evidence.
7. The cost model has verified effective-date coverage through 2026-09-09, Decimal arithmetic, explicit spread/slippage/impact assumptions, and no IEX-volume liquidity estimate. Unsupported dates fail instead of extrapolating regulatory schedules.
8. Sources are pinned and classified; unavailable pandas-ta is replaced by audited pandas-ta-classic. Restrictive/unlicensed source is not copied. Dependency locks are distinct from the repository inspiration audit.
9. LLM use starts disabled at a zero budget. The local assistant exposes data summaries with timestamps and refuses causal news claims. No scheduled expensive jobs.
