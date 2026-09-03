# Student AI bot bridge

## Decision

Student OS Core is the source of truth going forward. It owns internal users, Telegram identity links, the shared first trial, credit balance, unlimited state, AI reservations/token totals, Telegram Stars payment credits, admin adjustments, and audit. The legacy bot database is preserved as an archive and rollback reference; historical balances are not automatically migrated.

The Telegram bot remains a presentation/transport adapter. It never imports `bot.py` into Core and, in bridge mode, never writes a second balance after a Stars payment.

## Service API

All bridge operations are `POST` under `/api/internal/v1`:

- `/products` returns the authoritative catalog: `task_help_1_v1` = 25 Stars / 1 credit and `task_help_5_v1` = 100 Stars / 5 credits.
- `/identity/resolve` maps a Telegram identity to one stable internal UUID.
- `/entitlement` returns trial, balance and unlimited state.
- `/study/text` performs reserve → canonical structured engine → token-accounted commit, with release on failure.
- `/payments/telegram-stars` validates product and Stars amount, then credits exactly once by Telegram charge ID.

Requests carry only Telegram external identity and operation data. Core never accepts an internal `user_id`, granted-credit count, unlimited flag, or trial state from the adapter.

## Authentication

`BOT_BRIDGE_SECRET` signs the exact body with HMAC-SHA-256 over:

```text
v2.POST.<endpoint path>.<unix timestamp>.<unique nonce>.<exact request body>
```

Headers are `X-Bridge-Timestamp`, `X-Bridge-Nonce`, and `X-Bridge-Signature`. Core uses constant-time comparison, a five-minute default freshness window, durable nonce replay rejection, a 64 KiB body limit before JSON parsing, and a basic per-process rate ceiling. Browser cookies and CSRF are not accepted as bridge credentials. The bridge returns 503 when its secret is absent. Old unbound signatures are rejected; deploy matching Core/bot revisions before manual cutover.

## Failure and idempotency

- Duplicate AI `request_id` never invokes the engine twice or consumes twice.
- Failed AI releases paid credits or restores the shared trial.
- Duplicate successful payment returns the original record without adding credits.
- Reusing a charge ID for different identity/product/amount is a conflict.
- Bot-side successful payments must enter its durable outbox before delivery; Core outage is retried later.

## Rollout

The bot adapter remains default-off with `STUDENT_OS_BRIDGE_ENABLED=false`. Until manual cutover, its existing behavior and database remain unchanged. Enable only after Core health, signed connectivity, owner access, product catalog, synthetic payment, synthetic AI, and outbox retry checks pass.

## Implemented Telegram adapter checkpoint

Bot `d0e048b` routes balance, Core catalog, text analysis, Stars pre-checkout and
successful payments behind the default-off flag. A separate SQLite outbox commits
payments before delivery, retries on startup/every 60 seconds in bounded batches,
and checks the exact Core receipt before marking delivered. Defense uses the same
structured result without another model call. Old photo/admin/referral callbacks
cannot mutate a shadow ledger in bridge mode. Legacy mode remains available.

`tests/test_bot_integration.py` loads the actual bot client/outbox against Core ASGI.
Set `STUDENT_AI_BOT_ROOT=C:\student-ai-bot` locally; CI checks out the pinned bot
commit. Synthetic fixtures prove Web↔Telegram identity/trial, credits, unlimited,
shared engine, duplicate request rejection, failure refund, Stars catalog checks
and durable outage delivery. This is not a live Telegram/payment acceptance test.

Manual cutover and rollback steps are in the bot's `docs/BRIDGE.md`. Keep the
outbox during rollback; disabling bridge pauses retries and must not discard paid
pending records. Production URL, credentials, owner verification and explicit live
restart remain manual prerequisites.
