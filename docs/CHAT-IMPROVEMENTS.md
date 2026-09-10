# Assistant improvements — implementation and deployment

Implemented across the web and native source. The assistant keeps explicit stock-scoped conversations, retrieves bounded question-matched evidence, and streams visible model text into durable pending messages. The same safe Markdown parser powers both clients. Deployment verification and physical-device/live-model acceptance are recorded separately in [the release review](../reviews/chat-improvements.md).

The model remains Terra and the monthly LLM cap remains $5. No model, billing, provider permission, or subscription change is required. No paid model evaluation was run during implementation.

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

Implementation details: streaming uses OpenAI visible-text events on the backend and authenticated client polling (~700 ms while generating). Stop display pauses presentation; generation and possible billing continue. Search covers titles, symbols and message text. Explicit summaries are dated question excerpts from up to 20 completed user turns, not a paid model-generated memory. Signal discussions preserve a backend-selected snapshot and stored chart; their interval cannot be changed through the API.

Evaluation: six fixed offline questions plus causal/security regressions are executable. `scripts/evaluate_chat_answers.py` scores manually captured answers without sending requests; recognized IDs, latency/cost and explicit human-review fields are separate. Successful cited live output, actual iPhone behavior and production verification are not inferred from fixtures. See [evaluation instructions](CHAT-EVALUATION.md).

Current deployment targets: `https://selery-web.vercel.app` and `https://selery-13rz.onrender.com`. Web passkeys are implemented separately; Render still needs `SELERY_PASSKEY_ORIGIN=https://selery-web.vercel.app` if not already configured. No new chat API key or service is needed.
