# SELERY non-negotiables

SELERY is research-only. It must never submit orders, simulate fills, track broker positions, synchronize a broker portfolio, or provide execution adapters, flags, tickets, or confirmation flows. Do not ask about adding execution. Flag any future request that conflicts with this restriction. Alpaca provides quotes, bars, and news only; reject non-paper ALPACA_ENDPOINT hosts at startup.

Python is authoritative for quantitative calculations. Generate TypeScript contracts from the Python models; both apps consume the same API client and design tokens. No provider secret may enter either client bundle. Never print .env values.

IEX volume-dependent features must fail closed in the backend and read "needs SIP data" in both apps. Never treat IEX quotes as NBBO. All datasets retain feed, timestamp, availability, and source provenance. Historical evaluation is signal-event research, without fills or virtual accounts.

The journal is user-authored only. Confidence is unavailable until calibrated. Outcomes must preserve ambiguity and missing-data states. No lookahead: signals use only finalized bars known at their timestamp.

Use independent subagents in separate git worktrees for parallel implementation tracks, at most three active subagents. Frozen shared contracts may only be changed by the integration agent; track-local decisions go in track notes. Tests are deterministic and offline. Live verification is an explicit separate operation.

Read the accepted scope in IMPLEMENTATION.md; it supersedes execution-related material in the original plan.md. Maintain reviews, PROGRESS.md, DECISIONS.md, and DEBT.md. Never label unverified deployment or real-device acceptance as complete.
