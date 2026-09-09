# Wave 4 — ML

Review date: September 9, 2026. This is a retrospective integration review. It does not claim that a complete nine-part review occurred before every earlier integration. The accepted research-only scope supersedes execution material in the original plan.

## 1. Spec compliance

DONE: Immutable causal feature snapshots, meta labels, purged/embargoed validation, calibrated baseline comparison, untouched holdout claims, guarded tabular registry/inference, optional SHAP, actual LSTM/GRU/Transformer training and sequence qualification are implemented.

PARTIAL / EXTERNAL: No qualified real-market model was established with the available fixtures. Sequence artifact persistence/promotion and full feature/SHAP/reliability UI remain unfinished; drift helpers are not continuous monitoring. Scheduled retraining stays disabled.

The row-by-row inventory is [requirement coverage](../docs/REQUIREMENT-COVERAGE.md). Every partial item remains in [debt](../DEBT.md), directly or through that detailed inventory.

## 2. Does it actually run

See [recorded terminal evidence](verification.md): clean npm installation, Next production build, native iOS/Android export, TypeScript checks, Python tests and production Chromium checks. Only local behavior was exercised. A deployment configuration file is not a deployed service.

## 3. Tests

The final Python run passed 166 tests and 23 subtests with 80% aggregate statement coverage. Exact terminal output and per-module gaps are in [verification](verification.md) and [coverage JSON](../docs/coverage.json). Three integrated browser tests and shared cache/reconnect/chart checks pass. Live stream and Redis worker still lack deterministic test coverage; separate Alpaca smoke evidence is not a replacement for lifecycle tests.

## 4. Lookahead audit

Feature availability/finality and source hashes are checked. Scalers fit on training folds only; both baseline and complex probabilities calibrate from OOF predictions. Holdout mutation tests preserve fitted parameters. Atomic claims reject repeated/overlapping holdout searches. Registry checks model activation/training/label timestamps against signal time.

## 5. Shared-code audit

Python owns cost, indicator, strategy, sizing and outcome mathematics. Clients consume generated types/runtime schemas and a shared API client, tokens, formatting, cache envelope and reconnect protocol. Both chart surfaces use the same bundled renderer and marker contracts. Native navigation/storage and web cookie proxy remain platform-specific. Dynamic metadata and duplicate platform presentation state are not a completed contract-parity audit.

## 6. Security

Authored source, documentation, generated contracts, built web/native bytes and all local Git history were scanned for configured credentials; authored source/history were scanned for prohibited endpoint references. The scanner's sole documentary exception is a path ending in a license filename. Provider access is restricted to fixed market-data hosts/operations. Web cookies are HttpOnly, native tokens use SecureStore, tickets are single-use/session-bound, and streams recheck revocation. Full results are in [verification](verification.md). No provider key is included here.

## 7. Honesty check

IEX labels remain visible and volume restrictions fail closed. SIP entitlement does not imply an unimplemented feature exists. Recorded fixtures remain stale, options samples synthetic, costs modeled, and missing confidence/statistics explicitly unavailable. The chart p95 is desktop synchronous update time, not an iPhone or network claim. Passing tests establish bounded behavior; they do not establish profitable signals or complete product acceptance.

## 8. What I would do differently

Model families should remain behind a single persistable qualification interface. Native library interaction caused a full-suite crash that isolated ML tests missed; the fixed one-thread policy and mixed-workload regression are necessary evidence, not proof of hosted training suitability.

## 9. Verdict

**FAIL for full wave acceptance.** The implemented local subset passes its recorded checks, but the partial requirements and pending evidence above prevent a full PASS. This is the first formal complete boundary review, not a second consecutive failed review. Do not approve a release or claim Waves 0–5 complete from these artifacts. Outstanding work is consolidated in [final review](../FINAL-REVIEW.md); future dependent release integration must first resolve the relevant failed boundary.
