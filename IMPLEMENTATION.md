# Accepted implementation scope

The September 9, 2026 research-only implementation plan supersedes the earlier plan.md where they differ. No execution, paper trading, simulated fills, broker positions, portfolio sync, or execution configuration exists. Alpaca is market-data-only. The exact disclaimer is: “Selery is research software that displays analysis. It does not execute, recommend, or place trades.”

Build a desktop Next.js web app and native Expo app sharing a typed client, schemas, formatting, and design tokens. Python FastAPI owns all quantitative logic and versioned REST/WebSocket endpoints. Use TimescaleDB, Redis/Arq, Docker Compose, Vercel, and Railway deployment configuration. Authentication is single-user. Both apps keep third-party secrets on the server.

Waves: 0 contracts, costs, fixtures and license audit; 1 both surfaces thin slice; 2 eight independent data/web/news/domain/research/strategy/mobile tracks; 3 historical event research; 4 point-in-time ML; 5 research chat, distribution, CI, monitoring and documentation. Reviews at boundaries are automatic. External deployment and real-device evidence may remain pending while independent work proceeds.

IEX is explicit for initial live and historical data. All volume-dependent features are disabled on IEX, including VWAP and volume-based alpha features. SIP datasets are separate. The forward tracker records target-first, stop-first, neither, ambiguous, and incomplete outcomes using immutable signal snapshots. Journal entries require explicit user saves. Sizing is informational.

Hosting target is approximately $5/month; costly compute is manually triggered and any increase is reported before provisioning. LLM access defaults to disabled with a $0 cap. Final guides: SETUP-REQUIREMENTS.md, WEB-GUIDE.md, MOBILE-GUIDE.md. Report unavailable data and external acceptance honestly.
