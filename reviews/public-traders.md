# Public Traders integration review — 2026-09-09

## 1. Spec compliance

Implemented private source-specific directory, paginated activity, manual eToro discovery/snapshot refresh, open-record detail, dated IEX context and activity-referenced chat on web and native. eToro has an original allowlisted adapter; Kinfo and AfterHour have visible pending states, qualification notes and unsent access drafts. No following relationship, account synchronization or execution was added. Three user guides, architecture, instructions, migration, license notes, decisions and debt are updated.

Real provider contracts remain provisional because permitted real payloads are unavailable. eToro application/user keys and data rights are absent. Full closed history, exact shares/CFD/currency classification and normalized performance comparisons are unavailable. No source is called operational.

## 2. Does it actually run

Next.js production build and iOS/Android exports passed. Both services were restarted locally at web port 3000/API port 8000. An authenticated real proxy request returned all three sources pending, an empty public registry and the preserved $5 LLM allowance. A separate disposable fixture API/web pair exercised real public routes, normalization, storage, charts and local chat through the Next proxy. Desktop layout was visually inspected at 1512×982 with clearly labeled synthetic examples. No real trader was displayed or real iPhone tested.

## 3. Tests

- Full Python suite: 211 passed, 83% aggregate statement coverage; Public Traders module 96% at that run. A subsequent revocation-during-LLM regression was added and passed in a focused 48-test run covering public traders/security/assistant. There are now 21 public-trader tests.
- All nine browser tests passed against a disposable fixture API and production Next build: existing workspace checks, actual authenticated proxy integration, source filters, pagination/UTC dates, detail/citations, hidden-tab revocation and snapshot polling with in-flight chat.
- Generated contracts `--check`, TypeScript, shared cache/reconnect tests and shared chart tests passed. Desktop synchronous chart p95 was 3.3 ms in the helper run; this is not iPhone interaction evidence.
- Authored/generated files, web/native artifacts and Git history passed the sanitized secret/endpoint scanner. `git diff --check` passed. CI now enables the disposable public fixture proxy test; hosted CI has not run.
- Two existing Starlette/HTTPX/AnyIO deprecation warnings remain. The sandbox prevented initial TSX IPC/Chromium launch attempts; the non-IPC Node invocation and authorized local Chromium run passed. No dependency installation or clean-install rerun was needed for this extension because dependencies did not change.

## 4. Temporal and data correctness

Opening time is distinct from observation time; unknown publication/synchronization values stay null. Future or naive opening timestamps are unavailable. Missing records become `no_longer_observed`, never confirmed exits. Corrections archive prior normalized payloads and preserve first observation. Profile/statistic age does not reset when only activity refreshes. Fixture/source/feed provenance remains explicit. No cross-provider return, realized profit or motive is inferred.

## 5. Shared-code audit

Python defines models and normalization; generated TypeScript schemas and the shared API client serve both clients. Web/mobile tracks used isolated worktrees with centrally maintained contracts. A shared activity reference drives backend evidence selection. Both chart surfaces retain existing rendering and attribution. Mobile navigation and browser cookie proxy are platform-specific; real-device parity remains pending.

## 6. Security and privacy

Backend-only credentials, fixed public eToro host, three GET-only operation families, username validation, redirect rejection, bounded payload size, sanitized HTTP errors, refresh spacing and cooldown are implemented. The endpoint scanner adds a narrow third-party public-user namespace exception; independent tests still reject private broker paths. API routes are authenticated/no-store. Public data is excluded from persistent client caches and clears on backgrounding. Detected access withdrawal purges current/revision records. Detail and LLM responses recheck access after awaited work. Source LLM permission is separate from data permission; existing atomic budget reservations, kill switch and no automatic retries remain active.

Provider withdrawal is only known when observed through a refresh or configuration change; no licensed push deletion channel is available. Backup retention/removal and multi-process coordination require production review before real release.

## 7. Honesty check

Default public mode stays live/pending; fixture import is explicit and synthetic records never reach paid LLM calls. All imported exposure remains unclassified rather than assuming shares. The chart may not cover the entry date and is separately identified as IEX. Local chat states exits, realized profits and motives are unavailable. Tests verify trusted prompt/evidence boundaries, not a guarantee about every future model answer. The prior OpenAI HTTP 429 is unresolved and no live paid public-activity analysis was attempted. Kinfo/AfterHour inquiries are unsent; no subscription was purchased.

## 8. Adversarial review and corrections

An independent integration review found six issues: missing Next proxy allowlist entry, revoked evidence surviving a chart await, absent market provenance in chat, indefinite desktop stale state, retained mobile directory search hiding activity, and refreshed activity falsely advancing profile-statistic timestamps. All were fixed before final integration checks. A further review added the LLM-await revocation check. Actual proxy tests now complement mocked UI tests so route wiring cannot be validated only by mocks.

## 9. Verdict and five largest remaining weaknesses

**PASS for the implemented local fixture-tested subset. PENDING for operational provider, live LLM, deployment and real-device acceptance.** One verified eToro source can release independently of Kinfo/AfterHour once the following evidence is available.

1. No permitted real eToro payload/credential verification or Kinfo/AfterHour access agreement; documented schemas and synthetic fixtures cannot establish operational access or stable username behavior.
2. Actual upstream freshness, complete coverage, withdrawal notification and licensed backup/removal policy remain unverified; refresh and throttling are manual/process-local.
3. Stock versus CFD, quote currency and entry-date coverage remain unverified, so reference returns, full history and richer performance comparisons are unavailable.
4. Successful cited Terra output and live adversarial exit/motive evaluation remain pending after OpenAI HTTP 429; prompt controls are not a proof against all hallucinations.
5. No real-iPhone public-record/gesture/deep-link evidence, signed distribution or externally verified deployment. Exports and local browser tests do not replace those checks.

See [source qualification and acceptance procedure](../docs/PUBLIC-TRADERS.md) and [setup requirements](../SETUP-REQUIREMENTS.md).
