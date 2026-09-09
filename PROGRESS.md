# Implementation progress

Updated September 9, 2026. Research-only scope is permanent; IMPLEMENTATION.md and AGENTS.md supersede execution material in plan.md.

The repository now contains a runnable Next.js desktop research application, Expo native application, authenticated FastAPI backend, scientific libraries, fixtures, storage/migration/worker configuration and deployment documentation. Alpaca read-only credentials, explicit IEX data and delayed historical SIP access were verified; no account query was performed.

Local verification: 166 Python tests plus 23 subtests pass, 80% aggregate coverage; web production build, both native exports, TypeScript, three production browser checks and shared chart/cache/reconnect tests pass. Clean npm installation reports zero known vulnerabilities. See [terminal evidence](reviews/verification.md).

**Waves 0–5 are not fully accepted.** Implemented behavior, missing code and external requirements are enumerated in [coverage](docs/REQUIREMENT-COVERAGE.md). The nine-part reviews are retrospective and mark full acceptance FAIL rather than retroactively claiming successful gates. The local subset passes; release/deployment/device acceptance and broader advanced integrations remain outstanding.

The requested [setup](SETUP-REQUIREMENTS.md), [web](WEB-GUIDE.md) and [mobile](MOBILE-GUIDE.md) guides are written. [FINAL-REVIEW.md](FINAL-REVIEW.md) identifies the five main weaknesses and [DEBT.md](DEBT.md) tracks remaining work. No cloud resource or paid LLM workload was enabled.
