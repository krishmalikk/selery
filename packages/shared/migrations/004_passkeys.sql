-- Public keys only. Private keys and biometric templates never reach SELERY.
CREATE TABLE IF NOT EXISTS auth_credentials (id VARCHAR PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, payload JSON NOT NULL);
