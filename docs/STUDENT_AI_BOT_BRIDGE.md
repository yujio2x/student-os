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
<unix timestamp>.<unique nonce>.<exact request body>
```

Headers are `X-Bridge-Timestamp`, `X-Bridge-Nonce`, and `X-Bridge-Signature`. Core uses constant-time comparison, a five-minute default freshness window, durable nonce replay rejection, a 64 KiB body limit, and a basic per-process rate ceiling. Browser cookies and CSRF are not accepted as bridge credentials. The bridge returns 503 when its secret is absent.

## Failure and idempotency

- Duplicate AI `request_id` never invokes the engine twice or consumes twice.
- Failed AI releases paid credits or restores the shared trial.
- Duplicate successful payment returns the original record without adding credits.
- Reusing a charge ID for different identity/product/amount is a conflict.
- Bot-side successful payments must enter its durable outbox before delivery; Core outage is retried later.

## Rollout

The bot adapter remains default-off with `STUDENT_OS_BRIDGE_ENABLED=false`. Until manual cutover, its existing behavior and database remain unchanged. Enable only after Core health, signed connectivity, owner access, product catalog, synthetic payment, synthetic AI, and outbox retry checks pass.
