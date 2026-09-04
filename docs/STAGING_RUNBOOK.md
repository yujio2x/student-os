# Staging migration — no cutover until every gate passes

Selected topology: see CLOUD_COSTS.md. One shared Essential-0, separate personal
Cedar Eco apps in eu. Never provision a second database for the bot.

## Storage

Core selects PostgreSQL when DATABASE_URL exists. Normal environment-loaded startup
rejects staging/production without that URL. Explicit Settings objects allow isolated
SQLite security fixtures in tests; deployment must use environment-loaded settings.
Heroku-managed connection values stay outside Git, stdout and Doppler config sync.

`app/migrations/postgres/001_initial.sql` is the versioned baseline. Entire pending
migration set applies in one transaction; advisory locking prevents startup races.
`schema_migrations` stores version/checksum/time. Checksum mismatch, a newer database
version or SQL failure blocks startup. Do not edit a deployed migration: add the next
number. No automatic downgrade, database deletion or import of the legacy bot DB.

Core uses bounded connection-per-unit-of-work (max 4 per process), TLS for remote
PostgreSQL, 10s connect/lock limits, 15s statement limit. It deliberately serializes
short repository transactions across processes for beta correctness. AI/network calls
are outside those transactions. Before increasing concurrency, measure and design
row-level locking; never simply remove the advisory lock.

Local PostgreSQL regression command: `python scripts/test_heroku_postgres.py`.
It captures the Core app's managed URL in memory and runs tests in generated test_*
schemas. Only those disposable schemas are removed; public data is never cleared.
CI independently uses PostgreSQL 16 and the same regressions. SQLite remains covered.

## Remaining preflight (not yet passed)

1. Outbox code/isolated PostgreSQL outage/restart/idempotency tests passed in bot
   6c6d425 and Core 933fe84; SAME DB attached to both apps. Cloud runtime acceptance
   still required. Do not start cloud polling beforehand.
2. Configure separate Doppler configs, Core-only AI key, shared strong bridge secret,
   Telegram OIDC and Sentry privacy filters. Preserve Heroku-managed DATABASE_URL.
3. Deploy Core, verify migration/restart persistence; deploy bot with worker=0.
4. Configure domain/ACM, real owner login, synthetic bridge/payment tests, real-device QA.
5. Backup local bot/queue; stop old polling only after all gates pass. Start one cloud
   worker, verify smoke; rollback by stopping cloud first and restoring local runtime.

No real Stars payment without separate authorization. Do not use health pings to keep
Eco Core awake. Monitor remaining hours and pending delivery counts without exposing
payment payloads. Retain PostgreSQL/outbox during rollback.
