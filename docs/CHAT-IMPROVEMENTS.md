# Assistant improvements, in implementation order

The existing stock assistant saves threads, accepts follow-up messages, fetches selected-timeframe charts and news, and sends bounded history to Terra on explicit request. It currently receives only the newest 20 bars, three points per Python indicator, one recent signal and three news items. At most ten complete exchanges/16 KB of history are included. There are no model tools for fetching more context mid-answer. These limitations matter more than stronger-sounding wording.

## 1. Readable answers and usable citations

Render a restricted Markdown subset on both clients so bold text and lists do not appear as literal punctuation. Disable raw HTML and unsafe URL schemes. Map inline source IDs to the actual supplied evidence; flag unknown IDs rather than linking invented sources. Open an evidence card showing provider, feed, timestamp and the exact supporting observation. Acceptance: malicious Markdown is harmless, unknown citations are identified, and web/native show equivalent text.

## 2. Context matched to the question

An intraday question and a next-session question need different context. Fetch bounded 5m/1h/1D data when appropriate; calculate session levels, ATR, scenarios and comparisons in Python. Supply an explicit exchange calendar, current timestamp, as-of timestamps and price-session labels. Do not call the newest 20-bar range the daily range. State missing premarket, corporate-action, news or feed coverage. Acceptance: stale and incomplete data cannot produce an asserted current setup; future-bar mutation cannot change past calculations.

## 3. Discuss the selected signal

Add an Ask about this signal action that sends an immutable signal ID and a dated chart range. The backend retrieves reference levels, horizon, original confidence/model provenance if available, and observed outcomes. Keep chart selection synchronized with the conversation. Acceptance: the assistant cannot silently switch signals, fabricate model probabilities or treat an outcome as known at signal time.

## 4. Clear research comparisons

For setup questions, compare supported scenarios by explicit evidence criteria: confirmation condition, invalidation, supplied analytical target and modeled cost assumptions. Explain when no scenario has adequate support. A qualitative setup preference must stay separate from calibrated target-first probability and any historical hit rate. Current confidence UI uses original backend scores only; it does not introduce a numerical ranking engine.

## 5. Better response and conversation controls

Stream visible answer text, show retrieval/generation state, and support stopping display without claiming provider billing stopped. Preserve idempotency and retained reservations when billing is uncertain. Add search/rename and optional explicit summaries of older threads; keep summaries attributed as conversation history, not current evidence. Test reconnect, repeated taps, foreground/background transitions and unknown provider outcomes.

## 6. Evaluate before changing models or budgets

Use a small fixed set of questions: next-session plan with stale bars, explain an existing signal, absent confidence, conflicting news, missing history, and requests to infer a public trader's motive. Measure supported citations, correct dates, missing-data honesty, follow-up continuity, latency and cost. The $5/month allowance and kill switch remain. Live paid evaluations are manual; no model change or added subscription is required for the first UI improvements.

Current external dependencies: private passwordless sign-in still needs a selected identity method and its configuration; Render deployment/device behavior must be verified separately. No chat improvements in this document are claimed implemented merely because they are listed here.
