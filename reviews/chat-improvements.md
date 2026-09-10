# Chat improvements release review

## 1. Scope

Implement and deploy the six improvements in docs/CHAT-IMPROVEMENTS.md: readable cited answers, question-matched context, selected-signal discussion, research comparisons, streaming/conversation controls and evaluation. Web and native source are integrated; no mobile signing/distribution or paid model evaluation is implied.

## 2. Runtime

Existing FastAPI/Next/Expo architecture, Terra model and $5 monthly LLM cap remain. The new calendar dependency is pinned, licensed and included in the backend image. Migration 005 records immutable conversation charts; startup initializes the new table. Root owns shared Python/TypeScript contracts; isolated implementation tracks supplied web, native/parser and context changes.

## 3. Validation

Full Python suite: 299 tests passed with 85% aggregate coverage before the final two scorecard tests; the subsequent focused run passed all 49 streaming/controls/scorecard/assistant tests. Context and conversation modules reached 92% and 97% coverage in the full run. TypeScript checks, four shared Markdown/parser tests, Next production build and iOS/Android exports pass. All 18 browser scenarios passed across the integrated run and the corrected Public Traders test rerun. The two initial Public Traders failures were outdated direct-link assertions/new citation fixture fields; the new evidence-card behavior passed its rerun. Source/artifact/history scans and contract generation checks pass. Dependency deprecation warnings remain, without test failures.

## 4. Quantitative integrity

Only finalized bars available at the answer's as-of time enter calculations. Tests mutate future data, exercise ATR warm-up, holidays, DST and early closes, and prevent incomplete five-minute coverage from becoming a claimed session range. IEX volume features stay disabled. SPY costs retain explicit spread assumptions; scenario preferences remain qualitative and separate from calibrated confidence or historical hit rates.

## 5. Evidence and shared behavior

Both clients use the same safe Markdown parser and native text components; HTML is never interpreted, unsafe URLs are blocked and unknown source IDs are flagged. Evidence cards preserve exact supplied observations and source metadata. Signal threads store a server-selected immutable snapshot plus dated chart, reject symbol/interval mismatches, retain unavailable confidence and distinguish later observed outcomes from signal-time facts. Summaries are explicit dated question excerpts, not invented model memory.

## 6. Security and failure handling

Independent review found that a direct API request could change a signal thread's interval; the backend now rejects it and a regression covers the rejection. Streaming generation is held in a task registry and shielded from HTTP disconnects, with shutdown/restart interruption handling. Partial responses are marked failed and excluded from history. Idempotent request IDs prevent duplicate spend; unknown provider billing remains reserved. Stop display only pauses presentation. Private transcripts clear on native background/auth failure; web auth failures clear retained display state. No execution tools or extra external messages were added.

## 7. Evaluation and resource honesty

Six fixed offline evidence cases are executable. The offline answer-scorecard tool lists unknown IDs and preserves missing human review, latency and cost as pending/unmeasured. Usage audit events record completion/first-text latency where measured. No live model-quality or factual-support result is fabricated from a recognized source ID. Real calls remain manual under the existing cap. No paid hosting/data subscription or budget increase was made.

## 8. Deployment and remaining weaknesses

Targets: web `https://selery-web.vercel.app`; backend `https://selery-13rz.onrender.com`. Deployment evidence is recorded separately after the release push. New `/api/release` and `/health` revision metadata allow read-only verification. The five most significant remaining weaknesses are:

1. Physical-iPhone gestures, lifecycle and streaming display have not been accepted on hardware.
2. A manually reviewed live six-case model evaluation has not run; source-ID matching alone cannot prove factual support.
3. Keyword-based bounded retrieval, three news items and incomplete IEX coverage can leave questions underspecified.
4. Generation/session coordination still requires one API process; multi-instance operation needs shared atomic coordination.
5. Original model provenance and data adjustment/extended-hours coverage can remain unavailable; question-excerpt summaries do not provide semantic long-term memory.

## 9. Verdict

Implementation passes local automated checks. The reviewed API interval mismatch is fixed. Production deployment status, physical-device evidence and live paid evaluation are distinct acceptance gates; only verified deployment results will be marked complete.

Reference: visible-text event handling and terminal response processing follow [OpenAI streaming documentation](https://developers.openai.com/api/docs/guides/streaming-responses).
