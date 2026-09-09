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

10. Full SIP capability flags now distinguish implemented functions from merely eligible data. Bar-aggregated typical-price VWAP is a historical approximation, not tick-exact VWAP; IEX remains disabled.
11. Missing regular-session coverage fails conservatively; ordinary weekends/DST are handled, but unverified holidays/early closes are not inferred. Annualized ratios are withheld on unexplained weekday gaps.
12. Forward confidence is captured at signal time and reused from immutable snapshots; historical bars never receive a later-trained model. SHAP remains explicit-request only.
13. Python optional model libraries were installed and tested locally. A modern Numba constraint and macOS OpenMP dependency were necessary. Torch sequence compute uses one CPU thread after a mixed-indicator/model regression exposed a native crash.
14. Fresh npm resolution uses a small original bounded CommonJS URI decoder in place of a vulnerable transitive decoder, plus compatible UUID/PostCSS overrides. Malformed encodings remain unchanged; valid decoding is tested. Final audit reports zero vulnerabilities.
15. The measured 255 MiB fixture API profile excludes databases/workers/training/cloud overhead; it does not justify a hosting-cost increase. All paid integrations remain off.
16. Retrospective wave reviews are marked FAIL for full acceptance where requirements are partial. This records the gate-process shortfall rather than claiming earlier complete PASS results. The three user guides describe the implemented subset and remaining dependencies.
