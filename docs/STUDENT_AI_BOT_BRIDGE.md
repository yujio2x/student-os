# Student AI bot bridge — read-only audit and integration plan

## Audit boundary

Repository `C:\student-ai-bot` was inspected read-only at HEAD `5a9ce776a6e60a3879f51263443d9c89c115f7c1`. It already had unrelated uncommitted changes in `app/bot.py` and untracked assets/outputs; Student OS did not alter, stage, or commit any of them.

Useful patterns confirmed:

- atomic credit consumption and explicit restoration on AI failure;
- idempotent payment delivery keyed by Telegram charge ID;
- minimum event payloads without task/answer content;
- owner checks on every admin command/callback;
- paginated user/payment views and atomic admin mutations with an audit row.

Patterns deliberately not copied:

- Telegram ID as the web application's user primary key;
- direct Telegram handler dependencies in web core;
- full task content in operational admin views;
- direct writes to the live bot SQLite database from an unproven bridge.

## Student OS entitlement boundary

`StudentAIEntitlementService` exposes:

- `get_balance(user_id)`;
- `reserve_credit(user_id, request_id)`;
- `commit_usage(request_id)`;
- `release_reservation(request_id)`.

The local implementation uses `BEGIN IMMEDIATE`, binds each request ID to one internal user, prevents negative balances, makes reserve/commit/release retries idempotent, and refunds only an uncommitted charged reservation. Unlimited accounts reserve without decrementing.

Its source is explicitly `local-unconnected`. It is not yet the payment source of truth and therefore is not wired to block Student AI. Schedule, Deadlines, Today, Calendar, Settings, export, and other organization features never call this service.

## Safe live bridge plan

1. Backfill `external_identities(provider='telegram')` only from a reviewed mapping; never infer users from browser payloads.
2. Choose one ledger owner. Recommended first beta: the existing bot database remains authoritative for Telegram balances.
3. Add a narrow adapter/service API that reads and reserves by verified Telegram identity with request idempotency; do not attach both processes as competing writers to the same SQLite file.
4. Reconcile reservations, completed usage, releases, payments, and admin adjustments in a staging copy before any live migration.
5. Enable enforcement only after mismatch, retry, failure-refund, and concurrency tests pass against that adapter.

External blockers: production bot/client credentials, registered domain/redirect URL, an approved mapping/migration window, and a staging copy of the live ledger. None justify modifying live data now.
