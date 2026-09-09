# Desktop web track

Owned surface: apps/web. Shared quantitative logic and generated models remain unchanged. The renderer is imported from the integration-owned shared package.

Implemented: password login through same-origin Next proxy, HttpOnly session forwarding, authenticated watchlist, feed badges on quote/volume displays, finalized candle chart with EMA9/21 and RSI14, shared clickable/hover signal markers, reference-level detail panel, historical replay, source-linked news, backend-enabled strategy selection, historical study report with cumulative return percentage chart and JSON export, outcome cohort table, explicitly saved manual journal, backend sizing calculator, alert inbox, read-only research assistant, domain/model availability, settings, command palette, URL ticker/page state, cached data fallback, 30-second refresh and optional reconnecting WebSocket.

Design: shared sage/charcoal palette, packaged Inter/JetBrains Mono fonts, responsive dense panels, accessible labelled native form controls, keyboard Enter signal selection, Cmd/Ctrl+K symbol/page navigation and Escape dismissal. Tailwind utilities use shared tokens. Context panel supports browser resize on desktop. Persistent disclaimer and TradingView attribution remain visible.

Secrets: browser requests use same-origin `/api/v1`; the server proxy uses `SELERY_API_URL` and forwards cookies only to that configured server. The web login response removes the bearer token. Provider credentials never enter this package. `NEXT_PUBLIC_SELERY_WS_URL` is an optional public WebSocket URL, with one-time tickets fetched through the authenticated proxy. No credentials are stored in browser storage. Cached research responses are cleared on sign out.

PWA: standalone manifest and SVG brand icon included. Offline research cache becomes available after authenticated use; initial login still requires the backend. Full offline shell/service-worker installation and raster Apple icons are pending rather than represented as complete.

External acceptance remains pending: Vercel deployment, real browser interaction evidence, measured chart interaction p95, and API live entitlement verification. The native track owns device acceptance.

Verification: `npm run typecheck --workspace @selery/web` passed. `npm run build --workspace @selery/web` passed on Next.js 15.5.25; static main page, dynamic proxy, 186 kB initial page JS. Network-restricted install required approved escalation. Install reported two dependency vulnerabilities; integration agent should inspect the final unified lockfile audit before acceptance. No browser/device evidence claimed.
