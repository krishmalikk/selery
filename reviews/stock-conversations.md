# Stock conversations implementation review

Tone follow-up: the user reported a visible AAPL model response prefaced by a canned refusal. Shared instructions now request direct conditional setup analysis, while preserving research-only scope, evidence citations, Python-derived calculations and explicit stale-data limitations. No current best-setup ranking may be inferred from stale or insufficient context. Existing assistant/conversation tests pass (51); source/history secret scan and whitespace checks pass. These mocked tests verify request plumbing, not model adherence to the new tone. No paid evaluation was run. Suggested live acceptance cases: a normal next-session question, stale observations, requests for unsupported win rates/targets, and a short follow-up. Older billing-blocker statements in this review describe the earlier diagnosis; the reported answer does not independently establish current credit balance or factual correctness.

## 1. Spec compliance

Both clients require an explicit stock selection before opening a saved conversation. Each thread keeps its stock, message history and chart context. Desktop shows chart and chat together; native keeps a compact chart above the conversation and composer. Users can create, reopen and delete conversations. The separate public-activity question flow remains available.

## 2. Does it actually run

Next production build and iOS/Android exports passed. Production-browser checks exercised saved multi-turn threads, chart interval changes and the authenticated web proxy against an isolated fixture backend. This establishes local application behavior, not live model generation or physical-device acceptance.

The normal local backend and web app were restarted. Authenticated requests through port 3000 returned HTTP 200 for listing, creating, reading and deleting a temporary SPY conversation; the $5 cap and LLM enablement were preserved. The temporary record was removed and no paid model request was sent.

## 3. Tests

The full Python suite passed 237 tests with 83% aggregate coverage (conversation module 95%). Subsequent review fixes passed a 26-test conversation/API run; the final focused conversation suite passed all 14 tests, including oversized history, provisional observations and Python indicator context. Generated-contract parity passed. All 14 integrated browser tests passed, including five conversation tests and the existing public-trader/workspace checks. Web production build and both native exports passed after client integration.

Coverage includes explicit symbol validation, thread isolation, pagination, idempotent requests, concurrent/pending turns, persisted failures, restart recovery, deletion, bounded history, billing errors, stale charts and pending-message polling. Browser model responses are mocked; proxy integration uses explicitly disabled local mode. No paid OpenAI diagnostic was run for this change.

## 4. Lookahead audit

Python supplies chart indicators, closed-bar signals and dated news. A forming bar is labeled provisional and cited using its observation time, rather than its future finalization boundary. Historical assistant responses retain their original dates and citations in model history. Current observations are retrieved afresh per turn; chat does not see the user's crosshair or panned viewport.

## 5. Shared-code audit

Canonical Python conversation models generate TypeScript types/runtime schemas. Both clients use the shared API client and chart contracts. Migration 003 adds private conversation/message storage. The backend provides stock scope and accepted conversation history; clients cannot submit replacement history or change an existing thread's stock.

## 6. Security

All conversation routes require authentication and return private, non-cacheable responses. Credentials remain backend-only. Model requests use explicit bounded history with provider storage disabled, existing atomic budget reservations, kill switch and the approved $5 monthly cap. Idempotent retries cannot repeat a completed paid request. Failed/interrupted requests remain visible without a fabricated assistant response or automatic paid retry. Deletion removes active records; backup retention is separate.

Final source/artifact/history scan passed for 229 authored files and 173 build artifacts. Git whitespace checks also passed.

## 7. Honesty check

Charts retain IEX, stale and provisional labels. Model context contains the latest 20 bars, recent Python indicators and limited news, rather than an unlimited historical dataset. At most ten recent complete exchanges and 16 KB of history are sent; an oversized recent exchange is explicitly truncated. The last live OpenAI diagnosis remains HTTP 429 `credit_balance_exhausted`. A successful cited live conversation remains pending until account credits are available. Native export is not iPhone gesture/keyboard evidence.

## 8. What I would do differently

Independent review found that an oversized answer could remove the most recent exchange from context and that forming-bar citations could use a future availability boundary. Both were corrected and regression-tested. Shared durable coordination is needed before multiple API processes; transcript search, streaming replies and device accessibility verification remain future work.

## 9. Verdict

**PASS for the implemented local conversation flow; external acceptance pending.** The request is implemented on both surfaces and covered by local tests. Live funded Terra conversation output, real-iPhone behavior and hosted deployment are not claimed. This extension does not close the broader outstanding wave requirements.
