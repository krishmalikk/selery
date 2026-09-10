# Public Traders implementation and access qualification

Latest follow-up: imports and on-demand OpenAI sharing are enabled by explicit user instruction. Live eToro directory/snapshot requests returned HTTP 200, importing 11 profiles and 122 open observations from one trader. Real iPhone acceptance remains pending. OpenAI processing is configured but the live diagnostic returned `credit_balance_exhausted`; a billing top-up is required before successful model verification. These results supersede the initial pending-access snapshot below. See [enablement/billing review](../reviews/etoro-enabled-openai-billing.md).

Updated 2026-09-09. This extension stores authorized third-party public research observations. It does not connect to the user's brokerage state, follow traders, or execute anything. The existing disclaimer remains on both clients.

## Operational status

| Source | Code and access status | Remaining evidence |
| --- | --- | --- |
| eToro | Original GET-only adapter implemented; supplied credentials accepted by the metadata endpoint (HTTP 200). Storage/display permission remains pending | Permitted real trader payload, identifiers/pagination, stock versus CFD/currency interpretation, measured freshness, retention/LLM permissions and correct display on both clients |
| Kinfo | Pending; no scraper or speculative API adapter | Approved API/feed/export, schema, price, retention and OpenAI processing rights; inquiry drafted but unsent |
| AfterHour | Pending; no scraper or speculative API adapter | Authorized public-activity feed and sharing rights, schema, price and removal requirements; inquiry drafted but unsent |

No source is operational or release-accepted yet. Source status `configured` means configuration is present, not that real-data acceptance passed. The supplied `ETORO_PUBLIC_KEY`/`ETORO_PRIVATE_KEY` aliases now load correctly; an explicit instrument-metadata probe returned HTTP 200 ([evidence](etoro-verification.json)). No public trader was fetched or stored by that probe, so public-profile entitlement and storage/display/OpenAI permissions remain pending. No subscription was bought and no inquiry was sent. Mocked HTTP and synthetic examples establish implementation behavior only. Full closed history is unverified and is not imported.

## Provider qualification

The [eToro public-user schema](https://api-portal.etoro.com/api-reference/users-info/get-user-live-portfolio) documents opening time, rate, instrument, direction, leverage and allocation. Those fields are not proof that a particular instrument is shares, or that its quote currency matches an Alpaca reference. SELERY therefore labels exposure unclassified until this is validated. Public response documentation does not itself grant storage, display or LLM-processing permission.

[Kinfo terms](https://kinfo.com/terms) prohibit scraping; request an approved feed instead. [AfterHour's FAQ](https://www.afterhour.com/) restricts sharing brokerage data; the existence of public posts does not establish third-party feed rights. The drafts in `docs/access-inquiries/` cover the authorization gaps and must remain unsent until separately authorized.

The eToro adapter uses a fixed public API host and exactly three kinds of GET operation: current-year public trader rankings, a named person's published open records, and instrument display metadata. Requests have application/user headers and a unique request ID. There are no generic proxy, account or execution methods. Names are validated before constructing paths. Redirects are rejected, payloads are capped at 4 MB, requests are spaced by at least 1.1 seconds, and HTTP 429 starts a bounded cooldown with no automatic retry. Run a single API process: rate limiting and the refresh mutex are process-local.

## Data semantics

- Source identity is `source:username`, with eToro names case-normalized; equal display names never merge people. Provider username renaming and stability must be verified before a real release.
- Directory refresh imports one provider page (20 records); subsequent refresh imports the next page and wraps after the final page. Search/pagination apply to the locally imported registry, not all possible provider users. Only ranking entries typed `trader` are imported.
- Select a trader and explicitly refresh their public activity. Each response is treated as an open-record snapshot, capped at 1,000 records. Nested copied allocations are excluded to avoid false attribution.
- Observation timestamps mean SELERY observed a snapshot; opening, publication and synchronization times are separate. Missing publication/synchronization times stay null. Refreshing activity does not advance the date attached to old profile statistics.
- Identical duplicate IDs collapse. Conflicting duplicates or missing stable IDs reject the snapshot without replacing existing records. Corrections archive the previous normalized record and increment its revision; first observation remains immutable.
- Disappearance changes status to `no_longer_observed`, never to sold. Exit price, quantity, realized profit and motive remain unavailable. Polling cannot recover trades that open and close between snapshots.
- Instrument display symbols enable a dated IEX reference chart. All imported exposure currently stays `unclassified`; currency and return comparison remain unavailable. The chart is recent daily context (200 bars), and may not include an old opening date. Its feed, observation time, stale/fixture status and TradingView attribution are separate from trader data.
- Provider statistics are attributed risk score/copier count only; no independent broker verification, normalized performance ranking or inferred realized return is claimed.
- Records are marked stale after five minutes, on a provider error, or whenever synthetic. This is SELERY observation age, not measured upstream latency. Actual provider freshness remains unverified.
- HTTP 401/403 conservatively purges all stored eToro public data; a named-user 404 purges that person's records and revisions. Explicit private flags also fail closed. Disabling the data-use flag hides and purges records on the next registry request. Revocation must first be observed: no push-based provider withdrawal channel is implemented. Backups must follow the eventual provider removal agreement.

## Contracts, persistence and API

Canonical models live in `packages/shared/python/selery_shared/models.py`; regenerate with `npm run contracts`. They are provisional until permitted real payloads validate the documented eToro schema. Generated TypeScript runtime schemas and the shared client serve both surfaces.

Migration `002_public_traders.sql` creates `public_traders`, `public_activity` and `public_revisions` with indexed JSON payloads. SQLite uses the same SQLAlchemy table shapes. Current and revision data are removed together on detected withdrawal. No raw provider response, avatar, personal credentials or chat transcript is stored by this feature.

| Authenticated route | Purpose |
| --- | --- |
| `GET /api/v1/public-traders/sources` | Pending/configured/error/fixture status and permissions |
| `GET /api/v1/public-traders` | `q`, `source`, `limit`, `offset` directory filters |
| `GET /api/v1/public-traders/activity` | Same pagination plus `trader_id`, `symbol`, `date_from`, `date_to` |
| `GET /api/v1/public-traders/activity/{id}` | Record, source trader and optional dated chart; `include_chart=false` reads stored evidence only |
| `POST /api/v1/public-traders/refresh` | Empty/null `trader_id` imports a directory page; a trader ID refreshes their activity |
| `POST /api/v1/chat` with `activity_id` | Retrieves current authorized evidence server-side and answers on request |

Opening-date filters use inclusive UTC calendar dates and exclude unknown opening dates. Public routes/chat use no-store responses. Public records do not enter either client's persistent offline cache. Web revalidates stored evidence; native clears it on blur/background. Existing market cache behavior is independent.

## Chat and budget

Without source LLM permission, users get a deterministic cited local summary. Synthetic public records never trigger a paid model. With `SELERY_ETORO_LLM_ALLOWED=true`, active eToro data rights and the existing enabled/funded OpenAI configuration, the backend sends only the selected activity, its profile statistics, limitations, market provenance and citation IDs. Activity chat supports one response, not a multi-perspective run. User-supplied activity IDs are authenticated and checked against current permissions; client-supplied symbol does not override record identity.

Terra receives trusted instructions to keep exits, motives and missing fields unavailable and to label hypotheses. Python does all quantitative work; cross-provider returns remain unavailable without verified comparability. There are no execution tools. The existing $5/month atomic reservation, kill switch, provider `store:false` and no-automatic-retry policy remain in force. Tests check evidence boundaries and local answers, but live adversarial LLM behavior is not accepted until evaluated against real permitted records. The prior OpenAI HTTP 429 remains unresolved; no paid public-activity request was attempted during this implementation.

## Real-data acceptance procedure

1. Obtain eToro application/user credentials and written terms covering discovery, private storage/display, refresh/caching, removal and selected-record OpenAI use. Enable only permissions actually granted.
2. Refresh one directory page; compare stable IDs, pagination and links with the provider. Refresh one eligible public trader; inspect all normalized fields against the authorized original response. Record whether shares/CFD and currency can be established.
3. Measure upstream timestamps and SELERY observation delay across several authorized refreshes. Exercise public/private changes and retention removal. Do not classify an absent open record as a close.
4. Display the same real permitted record on web and an iPhone, including dated chart limitations. Capture sanitized evidence without credentials. Only then mark that source operational. Kinfo/AfterHour can remain pending.
5. Resolve OpenAI billing/rate-limit access and independently collect a successful cited activity response. Evaluate adversarial questions about exits, motives and source instructions before LLM acceptance.

No infrastructure increase is needed for the fixture implementation. Actual live refresh storage, memory, and source pricing remain unmeasured; do not infer that the existing hosting budget covers paid data.
