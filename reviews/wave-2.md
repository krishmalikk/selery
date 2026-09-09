# Wave 2 — Parallel breadth

Review date: September 9, 2026. This is a retrospective integration review. It does not claim that a complete nine-part review occurred before every earlier integration. The accepted research-only scope supersedes execution material in the original plan.

## 1. Spec compliance

DONE: Isolated A–H tracks produced adapters/archive replay, chart layouts, news analysis, SPY domain calculations, manual journal/sizing/alerts, strategy libraries, 87 nonbinary alpha formulas and native integration.

PARTIAL / EXTERNAL: Several advanced strategies, data contexts and alpha evaluations remain Python-library features without complete HTTP/UI workflows. General ingestion scheduling, broader chart controls and original mobile breadth remain partial. Missing entitled inputs are explicitly unavailable.

The row-by-row inventory is [requirement coverage](../docs/REQUIREMENT-COVERAGE.md). Every partial item remains in [debt](../DEBT.md), directly or through that detailed inventory.

## 2. Does it actually run

See [recorded terminal evidence](verification.md): clean npm installation, Next production build, native iOS/Android export, TypeScript checks, Python tests and production Chromium checks. Only local behavior was exercised. A deployment configuration file is not a deployed service.

## 3. Tests

The final Python run passed 166 tests and 23 subtests with 80% aggregate statement coverage. Exact terminal output and per-module gaps are in [verification](verification.md) and [coverage JSON](../docs/coverage.json). Three integrated browser tests and shared cache/reconnect/chart checks pass. Live stream and Redis worker still lack deterministic test coverage; separate Alpaca smoke evidence is not a replacement for lifecycle tests.

## 4. Lookahead audit

Price features use past/current finalized observations. Confirmed pivots are timestamped at confirmation. Alpha context requires point-in-time VWAP/capitalization/groups; volume formulas fail closed on IEX. Cross-sectional studies require supplied historical universes; news deduplication compares only previously observed stories.

## 5. Shared-code audit

Python owns cost, indicator, strategy, sizing and outcome mathematics. Clients consume generated types/runtime schemas and a shared API client, tokens, formatting, cache envelope and reconnect protocol. Both chart surfaces use the same bundled renderer and marker contracts. Native navigation/storage and web cookie proxy remain platform-specific. Dynamic metadata and duplicate platform presentation state are not a completed contract-parity audit.

## 6. Security

Authored source, documentation, generated contracts, built web/native bytes and all local Git history were scanned for configured credentials; authored source/history were scanned for prohibited endpoint references. The scanner's sole documentary exception is a path ending in a license filename. Provider access is restricted to fixed market-data hosts/operations. Web cookies are HttpOnly, native tokens use SecureStore, tickets are single-use/session-bound, and streams recheck revocation. Full results are in [verification](verification.md). No provider key is included here.

## 7. Honesty check

IEX labels remain visible and volume restrictions fail closed. SIP entitlement does not imply an unimplemented feature exists. Recorded fixtures remain stale, options samples synthetic, costs modeled, and missing confidence/statistics explicitly unavailable. The chart p95 is desktop synchronous update time, not an iPhone or network claim. Passing tests establish bounded behavior; they do not establish profitable signals or complete product acceptance.

## 8. What I would do differently

The frozen contracts helped independent tracks, but integration should have exposed complete end-to-end workflows before adding more standalone methods. Broad formula coverage is not evidence of empirical robustness.

## 9. Verdict

**FAIL for full wave acceptance.** The implemented local subset passes its recorded checks, but the partial requirements and pending evidence above prevent a full PASS. This is the first formal complete boundary review, not a second consecutive failed review. Do not approve a release or claim Waves 0–5 complete from these artifacts. Outstanding work is consolidated in [final review](../FINAL-REVIEW.md); future dependent release integration must first resolve the relevant failed boundary.
