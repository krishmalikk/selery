-- Private research conversations, independent of the manually saved journal.
CREATE TABLE IF NOT EXISTS conversations (id VARCHAR PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, payload JSON NOT NULL);
CREATE TABLE IF NOT EXISTS conversation_messages (id VARCHAR PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, payload JSON NOT NULL);
CREATE INDEX IF NOT EXISTS conversation_messages_thread_idx ON conversation_messages ((payload->>'conversation_id'));
CREATE INDEX IF NOT EXISTS conversations_updated_idx ON conversations ((payload->>'updated_at'));
