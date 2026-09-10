# Public trader fixture provenance

`etoro.json` contains entirely synthetic people, identifiers, prices, statistics and open records, authored for deterministic tests on 2026-09-09. It is not recorded provider data, entitlement evidence or a real trader's performance. Source links lead to the schema documentation, not invented public profiles.

Its shape follows the documented public rankings, public-user open records and instrument display metadata. The envelope SHA-256 covers `json.dumps(data, sort_keys=True, separators=(',', ':')).encode()`; import rejects a mismatch. Cases include an unmapped instrument, missing prices and timestamps, differing identities and multiple symbols. Tests separately introduce duplicates, corrections, disappearance, access withdrawal and rate limits.

The application requires an explicit backend `SELERY_PUBLIC_TRADERS_MODE=fixtures` and manual refresh to import these examples. Synthetic records are always stale, visibly labeled and excluded from paid LLM requests. Default mode is live/pending.
