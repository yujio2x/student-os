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

Its default source is explicitly `local-unconnected`. Student AI now fails closed unless the current internal user has a verified Telegram link and the entitlement source reports connected. A connected adapter follows reserve → engine → token-accounted commit, with release on engine failure. Schedule, Deadlines, Today, Calendar, Settings, export, and other organization features never call this service.

The current `local` source is an isolated development/staging fixture, not the payment source of truth. Reusing a processed request ID is rejected before a second engine call; a future authoritative adapter may instead return a safely cached response.

## Safe live bridge plan

1. Backfill `external_identities(provider='telegram')` only from a reviewed mapping; never infer users from browser payloads.
2. Choose one ledger owner. Recommended first beta: the existing bot database remains authoritative for Telegram balances.
3. Add a narrow adapter/service API that reads and reserves by verified Telegram identity with request idempotency; do not attach both processes as competing writers to the same SQLite file.
4. Reconcile reservations, completed usage, releases, payments, and admin adjustments in a staging copy before any live migration.
5. Enable enforcement only after mismatch, retry, failure-refund, and concurrency tests pass against that adapter.

External blockers: production bot/client credentials, registered domain/redirect URL, an approved mapping/migration window, and a staging copy of the live ledger. None justify modifying live data now.

The detailed old-bot → shared domain → Telegram/web mapping, photo compatibility fixtures, rollout stages, and rollback procedure are in `docs/STUDENT_AI_ARCHITECTURE.md`.
