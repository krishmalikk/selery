# Track B — persistent chart interaction and shared client state

Both chart surfaces now call the same renderer's `update(data)` method. Ordinary backend refreshes retain the chart instance, visible time interval and user-adjusted oscillator pane heights. Symbol/timeframe/feed or displayed indicator structure changes rebuild the renderer; indicator toggles retain the viewport. Rendering uses only supplied Python indicator series, including EMA 9/21, SMA 50, Bollinger bands, RSI 14, MACD, ATR 14 and entitled VWAP. No quantitative formulas run in the clients. Replay filters markers by both event time and availability at the displayed bar.

Desktop adds individual backend-indicator toggles, price/trend, momentum and volatility presets, an explicit Save layout action and My saved layout restore option. Saved layouts are browser-local and removed on sign-out. Optional SPY/QQQ comparison fetches an actual second chart response, with its own source/feed/freshness label and independent price scale. Missing series show unavailable; VWAP stays disabled with “needs SIP data” on IEX. Oscillator panes have draggable separators. Signal details identify the symbol, including comparison selections. The web refresh effect no longer temporarily unmounts the chart on every stream message.

Web and mobile now use the shared `encodeCache`/`parseCache` freshness and schema rules and `connectResearchStream` ticket/reconnect policy. Platform wrappers retain only React lifecycle and storage/WebSocket adapters. Desktop drops obsolete requests after symbol/timeframe changes. Mobile Settings calls authenticated server registration and reports the returned registration state, without suggesting that registration proves delivery.

## Verification

Both web and mobile TypeScript checks pass. `tests/test_chart_helpers.ts` bundles the real renderer and exercises it in offline headless Chromium. Tests verify replay cutoff, source immutability, late signal availability, stable indicator-key identity, instance reuse, visible-range preservation, pane-height preservation, rebuild behavior and idempotent disposal. All browser network requests are blocked.

A 2,000-bar synthetic renderer sample measured approximately **2.9 ms p95 synchronous update time** over 30 updates separated by browser animation frames. This is a desktop browser measurement, not touch-response latency or iPhone acceptance. Physical-device pinch, pan, crosshair, long-press and end-to-end chart latency remain pending.

Integration must regenerate the mobile local HTML bundle with `npm run chart:bundle --workspace @selery/mobile`; the generated artifact is owned by the integration agent. The chart helper test requires installed Playwright Chromium and esbuild. Portable cache parsing accepts a structural `parse` interface so workspace packages can use their pinned Zod versions without recursive cross-version type comparisons.
