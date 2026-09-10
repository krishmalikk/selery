# Final integration review — September 9, 2026

The later Public Traders extension is documented in [its nine-part review](reviews/public-traders.md). Local implementation/testing does not change the full-scope acceptance status below. Its five leading unresolved weaknesses are real provider authorization/payload validation, upstream freshness and withdrawal detection, instrument/currency classification, live cited LLM verification after HTTP 429, and real-device/deployment evidence.

**The implemented local research workspace runs, but the full requested Waves 0–5 scope is not accepted.** The six retrospective [wave reviews](reviews) explicitly mark full acceptance FAIL where requirements remain partial. This document is an integration report, not a claim of completed deployment or product release.

## Implemented and locally verified

The repository contains the authenticated Next.js desktop app and Expo native app, one Python research API, shared generated contracts/client/tokens/chart renderer, explicit IEX data restrictions, immutable forward signals, historical signal-event reports, manual journal/sizing, news/context libraries, strategy and alpha libraries, optional calibrated model tooling, bounded optional assistant, notification adapters and deployment/operations configuration. The exact research-only disclaimer appears on both surfaces. No broker execution or broker-state capability exists.

The final Python suite passes 166 tests and 23 subtests with 80% aggregate statement coverage. Both clients typecheck; Next production compilation and iOS/Android exports pass. Three production Chromium workflows and shared cache/reconnect/chart regressions pass. Clean npm installation/audit reports zero vulnerabilities. Credential scanning covers authored files, generated client builds and local history. [Recorded terminal evidence](reviews/verification.md) and [coverage](docs/coverage.json) provide scope and per-module limits.

Alpaca read-only authentication, IEX data, delayed historical SIP and news were verified in dated [provider evidence](docs/alpaca-verification.json) and [live smoke](docs/live-smoke.json). Historical SIP access does not imply live SIP. Local defaults remain labeled recorded fixtures.

## Five most significant weaknesses

1. **Full product breadth is unfinished.** Advanced context-dependent strategies, alpha studies, provider ingestion, some overlays/native details and deeper assistant/retrieval workflows are useful Python methods or partial integrations rather than complete client workflows. This is missing implementation, not solely missing API keys. The [requirement matrix](docs/REQUIREMENT-COVERAGE.md) names the gaps.
2. **Device and hosted operation lack acceptance evidence.** No real-iPhone gestures/p95/push receipts, signed TestFlight build, Vercel/Railway deployment, hosted CI or full Docker/Timescale/Redis run is claimed. Local bundles and screenshots cannot substitute. Signing/accounts and a suitable device/deployment environment are needed.
3. **Scientific evidence is limited by data and model integration.** Thin recordings cannot establish crisis robustness, publication/crowding effects, complete trial-family statistics or a useful calibrated market model. Sequence training/qualification exists, but artifact serving/promotion and complete explanation/calibration views remain unfinished. Unknown calendars and data gaps conservatively withhold metrics.
4. **Production durability and contract coverage need further work.** Single-process auth/observer state limits replicas. Same-feed provider/version archives need richer durable identity. Dynamic metadata needs full generated contracts; live stream and worker lifecycle paths lack fixture coverage. Monitoring and PostgreSQL restore need operational validation.
5. **The planned gate process and release license audit are incomplete.** Track testing and focused reviews occurred, but complete nine-part boundary records were written retrospectively. They cannot establish prior acceptance. The source audit pins revisions and inventories notices/headers; it is not exhaustive file-level reuse clearance. Bundled chart/font notices and runtime dependency declarations are present, while full release packaging still needs review.

## Resource and safety observations

The local fixture API profile peaked at 255.06 MiB RSS; this excludes external database/Redis/worker/network/model/cloud overhead. The $5/month target remains a target. No paid service or hosted training was enabled. LLM usage defaults off/$0 and reserves budget atomically before requests.

Review fixes included outcome symbol isolation, queue status ordering, requested model horizons, session-gap ambiguity, conservative annualization, WebSocket revocation, truthful SIP capability flags, TypeScript/Zod memory behavior and a mixed indicator/Transformer native-runtime regression. Existing current provider secrets were not printed or committed.

## Handoff

- [SETUP-REQUIREMENTS.md](SETUP-REQUIREMENTS.md): credentials, accounts, resources, deployment/signing, costs and missing dependencies.
- [WEB-GUIDE.md](WEB-GUIDE.md): implemented desktop workflows, API, local/Vercel/PWA setup, testing and limitations.
- [MOBILE-GUIDE.md](MOBILE-GUIDE.md): native workflows, Expo Go, EAS/signing/TestFlight, gestures, caching, notifications and remaining acceptance.
- [DEBT.md](DEBT.md) and [requirement coverage](docs/REQUIREMENT-COVERAGE.md): remaining code and external evidence.

Use the local fixture workspace for review. Do not represent the unfinished scope as a fully completed or externally verified release.
