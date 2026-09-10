# Native stock conversations

- `/chat` now starts with an explicit stock symbol and a paginated saved-conversation list. Selecting a symbol route parameter only prefills the form; it does not create a conversation or call the LLM.
- Each thread fixes its stock. A compact native WebView chart remains above the scrolling transcript and composer, with 5m/1h/1D selection. The chart contracts, renderer, IEX badge, timestamps, fixture/stale labels, and TradingView attribution are shared with the chart screen. Keyboard display reduces chart height.
- Conversations are stored by the authenticated API. Message drafts, chart data, and loaded history remain in memory only and are cleared on blur/background. Foreground focused screens refresh read-only data every 30 seconds; navigation and polling never issue paid requests.
- Failed sends retain drafts, reload persisted message state, and preserve the request ID for uncertain transport errors. A confirmed failed user message permits a fresh manual attempt. The original timeframe is retained on an uncertain retry.
- Public activity chat remains separate and ephemeral through the existing `activity_id` route parameter; its source/withdrawal behavior is preserved. Clearing it now also clears its draft and error.
- NativeChart gained an optional height parameter; other chart screens keep the existing 420px default.

Validation: mobile TypeScript check passes. Final integrated export is performed by the integration agent. Real iPhone layout, keyboard avoidance, gestures, background/foreground, and screen-reader acceptance remain pending.

Device acceptance checks: start a stock conversation; exchange two turns; reopen it; compare timeframes while chatting; force a failed send and retry once; background during a request; return and inspect persisted history; verify scrolling/keyboard/chart on a small iPhone; delete a conversation and verify it disappears. No live paid requests were made during this track.
