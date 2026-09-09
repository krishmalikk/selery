# Track E — research observations, sizing and journal

The initial integrated API supplied immutable forward signal snapshots, deterministic target/stop/ambiguous/neither scoring, an informational risk/allocation sizing calculator, an explicitly user-saved journal, and audit rows. This isolated follow-up makes a missing intraday observation fail closed instead of allowing a favorable later threshold to stand in for the unknown sequence. Duplicate source bars do not advance the horizon twice.

Tests cover immutable snapshots, no automatic journal writes, zero-distance sizing rejection, target/stop ambiguity, pre-signal input exclusion, duplicate observations and a regular-session gap. Intraday gaps outside the regular session and historical vendor corrections still require exchange-calendar/revision reconciliation; the record does not claim that sparse IEX bars establish a consolidated price path. Captured outcomes are feed-specific observations.

No broker-state synchronization or execution capability exists. Future cohort comparisons must match strategy version, timeframe, horizon and feed; missing coverage is excluded and disclosed rather than counted as a success.
