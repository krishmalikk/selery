-- Dated chart snapshots for explicitly signal-bound research conversations.
CREATE TABLE IF NOT EXISTS conversation_charts (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    payload JSON NOT NULL
);
