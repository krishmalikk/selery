-- Authorized third-party public research records only. No personal brokerage state.
CREATE TABLE IF NOT EXISTS public_traders (id VARCHAR PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, payload JSON NOT NULL);
CREATE TABLE IF NOT EXISTS public_activity (id VARCHAR PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, payload JSON NOT NULL);
CREATE TABLE IF NOT EXISTS public_revisions (id VARCHAR PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, payload JSON NOT NULL);
CREATE INDEX IF NOT EXISTS public_activity_trader_idx ON public_activity ((payload->>'trader_id'));
CREATE INDEX IF NOT EXISTS public_activity_observed_idx ON public_activity ((payload->>'observed_at'));
