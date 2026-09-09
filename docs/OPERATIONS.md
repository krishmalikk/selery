# Operating the personal research service

Use one API process and one optional worker. Session revocation, stream tickets and observer ownership currently live in that process. Do not enable replicas until these are shared durably.

## Health and resource evidence

`GET /health` checks database connectivity and returns HTTP 503 on failure, without configuration or exception details. Configure Railway's health probe to this path. An optional external uptime monitor can use this public endpoint; no monitoring account is required for local use. Investigate `observer_error`, model audit events, queue failures and notification delivery records in the backend database. Logs and audits intentionally retain error types rather than provider bodies.

Run `.venv/bin/python scripts/profile_runtime.py` for a reproducible in-process fixture sample. [runtime-profile.json](runtime-profile.json) records the measured machine, Python version, 10 request samples per operation and peak RSS. The initial API sample peaked at 255.06 MiB; chart processing median was 50.44 ms with a 645.72 ms cold maximum. This excludes PostgreSQL, Redis, worker, training and cloud overhead. It does not establish a $5 monthly price. Inspect Railway memory/CPU/network and actual invoice estimates before changing the deployment resources. Scheduled training is disabled.

The shared chart's separate local Chromium update test measured p95 about 2.1 ms for 2,000 bars. This is synchronous chart update time on the development computer, not end-to-end network latency or iPhone touch evidence.

## Backups and recovery

For local SQLite, create a consistent snapshot without printing contents:

```sh
.venv/bin/python scripts/backup_sqlite.py data/selery.db data/backups/selery-YYYY-MM-DD.db
```

The destination must be new. The command uses SQLite's online backup API, checks integrity and sets owner-only permissions. Back up `data/raw` and `data/models` alongside the database; model metadata references artifact checksums. Keep backups outside an ephemeral deployment filesystem. Encrypt any off-machine copy: research notes and notification device tokens are private.

To restore, stop the API and worker, preserve the current database under a different filename, and copy the chosen backup to the configured SQLite path. Run an integrity check and start the API in fixture mode first. Verify journal counts, reports, model artifact hashes and `/health` before resuming live ingestion. Never replace an existing database while processes are using it.

For PostgreSQL, use `pg_dump` in custom format and `pg_restore` into a new database, supplying connection credentials through private environment/service configuration. Restore and verify in isolation before directing the application to the restored database. TimescaleDB extension/version compatibility must be checked in the Docker-capable deployment environment; that recovery path has not been exercised here.

## Incident controls

Set `SELERY_LLM_ENABLED=false` to disable requests immediately on the next settings load; maintain `SELERY_LLM_MONTHLY_CAP_USD=0` until funded. An invariant failure also writes the durable `llm-kill-switch` setting. Unknown provider billing outcomes retain their budget reservation and are never automatically retried. Reconcile provider usage against audit entries before any manual reset. Cross-month unresolved reservations need explicit operator reconciliation.

Set `SELERY_NOTIFICATIONS_ENABLED=false` to stop external alert delivery. Do not automatically resend an ambiguous delivery result. Device receipt checks require a configured development build and real receipt evidence.

If provider data stops, clients label stale/offline state and retain their permitted cached snapshot. The backend reconnects with backoff. Changing a feed starts a different dataset; never relabel an IEX archive as SIP. Archive conflicts are rejected rather than overwritten. An incomplete forward horizon stays incomplete.

Rotate the personal password and session secret in the backend environment to invalidate sessions. Restart after rotating the session secret. Provider credential rotation belongs only in the backend; rebuild neither client with provider keys.

## Verification boundaries

CI is supplied in `.github/workflows/ci.yml`; no remote GitHub Actions run is claimed. Browser production checks, Python tests, TypeScript checks, iOS/Android export and credential scanning run locally. Signed EAS builds, TestFlight, iPhone gestures/notification receipts, Docker Compose startup, Timescale recovery and hosted Vercel/Railway probes remain external acceptance steps in the setup guides.
