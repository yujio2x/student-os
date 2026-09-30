# One-Eco webhook cutover and rollback

Prepared 2026-09-30. This is an infrastructure runbook, not permission to print/copy secrets or run a real Stars charge.

## State and gates

The audit changed Bot worker formation to 0:Eco on September 30. Both runtimes had been idle because September's hours were exhausted. Do not scale the old worker up at renewal. New code defaults Core TELEGRAM_DELIVERY_MODE=disabled for rolling compatibility. Bot defaults to polling but retains its explicit CLOUD_POLLING_ENABLED latch, a shared PostgreSQL transport lease, and now refuses an existing remote webhook rather than allowing python-telegram-bot to delete it.

Go-live requires green Core/Bot CI (including existing PostgreSQL CI), tested commits deployed, owner-created webhook secret synced, positive new Eco quota and a confirmed stopped polling formation. Current code preparation is not evidence of live webhook activation. Build/release is separate from dyno execution; no one-off is needed to register the webhook.

Verified code checkpoint: Core bde6d98 / CI 36694595230 and Bot 93ef0de / CI 36692911514 are green, including PostgreSQL. Core source and docs may have a later documentation-only checkpoint commit. Heroku deploy did not run: automatic approval review rejected preparation deployment as premature, so explicit owner approval is the remaining deployment gate. The current old releases are Core v36/Bot v19; Bot ps confirms No dynos. Secret presence/sync and live webhook status have not been inspected. No setWebhook/deleteWebhook was executed.

## Repository ownership

Core's student_telegram package vendors exactly four adapter modules from the reviewed Bot commit recorded in manifest.json, with only their internal package imports rewritten. Core's script refreshes that snapshot explicitly; tests verify hashes. Core does not clone/import the complete Bot repo during deployment, execute app.bot, open its SQLite, or load another AI engine. CI pins the same Bot commit for cross-project tests. No circular build or deployment dependency.

## Owner-supplied configuration

Use existing authoritative Doppler stg configs and confirm Heroku sync. Never use Reveal or copy secret values via Codex. DATABASE_URL remains Heroku-managed, attached to the existing one database.

| Config | Key | Required value/action |
|---|---|---|
| student-os/stg | TELEGRAM_WEBHOOK_SECRET | Owner manually generates/enters 64 random allowed characters A-Z a-z 0-9 _ -; runtime accepts 32-256. Do not paste into chat. |
| student-os/stg | TELEGRAM_DELIVERY_MODE | disabled while preparing; webhook only after tested release and stopped pollers |
| student-ai-bot/stg | CLOUD_POLLING_ENABLED | false |
| student-ai-bot/stg | TELEGRAM_DELIVERY_MODE | webhook during webhook production; polling only for deliberate rollback |

Core already has TELEGRAM_BOT_TOKEN and BOT_BRIDGE_SECRET; no copying/rotation is required. Missing/invalid webhook config raises a key-name-only startup error. Secret token is verified server-side in X-Telegram-Bot-Api-Secret-Token with constant-time comparison, fail closed. No secret in endpoint URL.

## October 1 sequence

Wait until Billing actually shows a replenished pool. The documented reset is the first day of the month; the exact reset hour/timezone is not verified. Do not promise availability at midnight Asia/Qyzylorda.

1. Confirm Bot remains zero (`heroku ps --app student-ai-bot-ernar-beta`), no local poller, review app, Scheduler or one-off. Set polling latch false and Bot mode webhook in its authoritative config. Core webhook startup must acquire the SAME advisory lease 734923403; if a poller owns it, startup fails.
2. Deploy exact tested commits to existing apps. Confirm one Eco Core web and zero Bot worker. Keep Core mode disabled until secret presence/sync is confirmed. Do not start extra dynos for preflight. Deployment while exhausted can be prepared, but a successful build is not successful runtime health.
3. Owner creates TELEGRAM_WEBHOOK_SECRET if not already saved. After tested Core release, change Core mode to webhook. Config release restarts the ONE web; startup initializes journals/outbox, acquires transport lease and initializes Telegram client without polling. Confirm `/api/health` and owner login once.
4. Owner opens `/admin`, Telegram webhook section, clicks **Подключить webhook** once. Server registers canonical HTTPS origin + `/api/telegram/webhook`, secret token from server config, allowed_updates message/callback_query/pre_checkout_query, max_connections=2, drop_pending_updates=false. No credentials enter browser controls. Owner-only existing session + CSRF authorize the action.
5. Click **Проверить статус**. Expect registered=true, expected_origin=true, runtime_ready=true, pending_updates falling and no new delivery errors. Status exposes only booleans/counts, never raw provider error/URL/token/payload. Send `/start`, `/balance`, one text, its defense and feedback buttons, photo/confirm/select, `/buy` without paying. Confirm one answer/charge boundary with synthetic tests, not a real charge. Then inspect account dynos/resources and quota again. Leave worker zero.

Status button only requests on explicit clicks, not an uptime timer. Admin controls are operational tooling for this incident; product AI/pricing/entitlements are unchanged.

## Durability and precise boundaries

Webhook accepts POST application/json, authenticates before reading/parsing, streams at most 64 KiB, validates update identity, rejects malformed/conflicting IDs and returns non-2xx if durable persistence/runtime is unavailable. Unknown supported-future update kinds are acknowledged as ignored tombstones. Pre-checkout is special: fast webhook response invokes answerPreCheckoutQuery from Core's authoritative existing PRODUCTS, without slow AI/catalog HTTP. Telegram must receive an answer within 10 seconds; cold start may miss it, so purchase fails closed. No money is granted from pre-checkout.

Ordinary text, photo, callbacks and feedback enter telegram_jobs. The single serial consumer calls the Bot presentation adapter against the existing signed Core ASGI routes in-process, not public loopback HTTP or another service. It is bounded to one active update; payment retry is an independent bounded batch in the same process. Queue acknowledgement does not wait for OpenAI. In-process bridge waits for actual Core completion instead of orphaning work at the old 45-second routed-client timeout; webhook startup bounds provider I/O at 120 seconds per request with SDK automatic retries disabled. Jobs have unique update IDs/fingerprints, ownership, a 300-second lease renewed every 30 seconds, startup/stale recovery, three attempts with 30/60/90-second retry delay, and a persistent review state. Completed jobs remove raw update/effect results; context expires/deletes at 24h; completed dedupe tombstones remain seven days. Pending/review data is retained until safe reconciliation. Existing paid outbox rows are not deleted.

Successful_payment is persisted in the durable inbound job AND existing bot_outbox.payment_outbox before 2xx. A crash between writes causes non-acknowledgement and safe Telegram retry. The consumer also enqueues it idempotently. Payments retry independently of job/output success with the existing bounded batches/exponential backoff (up to one hour). Unknown response after Core commit stays pending; unique charge ID produces one credit grant on restart/retry. No HTTP/AI transaction holds a database lock.

AI Core stable message/callback/quote request IDs prevent repeated business charges. A per-job Core result cache and initial context snapshot allow safe replay after known completion. Telegram send effects record intent BEFORE sending, and completed responses are cached. A retry reuses the response instead of sending again. Telegram sendMessage has no general caller-provided idempotency key: crash/network loss after send but before receipt persistence is intrinsically ambiguous. Such effects move to review and never blindly re-send/re-bill. This intentionally does not promise both exactly-once visible delivery and automatic recovery of unknown external outcomes. The actual exactly-once boundary is Core's credit ledger; transport is at-least-once ingress and conservatively fenced outbound effects. Reconcile review counts manually with Core reservation/payment evidence; do not reset request IDs or delete intent fences to force replay.

Photo confirmation persists file_id/quote/context, not raw bytes; re-download has the same bound. Defense context and photo sessions survive process restart within their existing expiration windows. Per-job initial context makes partial dispatch replay deterministic. No runtime logs contain raw exceptions, Telegram URLs, credentials, payment/user payloads or AI assignments. HTTP client INFO logs are disabled to prevent token-bearing Bot API URLs. Sentry retains the existing content-free allowlist.

## Eco sleep and deployment behavior

Official Heroku documentation says inbound web traffic wakes a sleeping Eco web when hours remain. Retained September router lifecycle logs show actual Core wake to up in about 5-13 seconds, but this is historical Core startup, NOT a measured new webhook cold start. Telegram documents retries on non-2xx and at-most-24h retention, with no fixed retry interval or timeout SLA. Heroku initial response window is 30 seconds. Slow processing is removed from webhook response, but platform/DB/client startup can still cause retries/checkout expiration.

After activation, test once after >30 minutes without web/browser/bridge requests: observe actual idle through CLI (which does not ping the web), then owner sends one Telegram text and checks one answer; inspect redacted webhook status and router lifecycle. Record time from wake to readiness. Do not send keepalives to manufacture a pass. This test cannot be done during September quota exhaustion. Restarts re-open PostgreSQL journals; interrupted ownership becomes reclaimable, while effect fences prevent repeat charges/output. When Eco sleeps with queued jobs or pending payment retries, they remain durable but wait for the next wake; Eco provides no always-available execution SLA.

## Budget proof and operations guard

Only web.1 can run continuously. 30/31-day baseline is 720/744 h, below 1000 by 280/256 h. One-off tests, temporary rollback overlap and rolling restart overlap consume reserve; operational policy caps extras at 24 h/month, leaving at least 232 h in a 31-day month. This is a conditional capacity proof for the audited formation, not a promise against arbitrary future apps/operator scaling. Do not run always-on extra consumers, Heroku review apps/CI dynos/Scheduler, or paid queues. GitHub CI's disposable PostgreSQL does not consume Heroku hours/resources. Monitor Heroku usage via Billing/CLI without pinging the application.

Resource subtotal: Eco $5 + existing Essential-0 $5 = $10/month, within $13 monthly eligible Student credits ($3 margin, expected $0 cash excluding other charges/taxes). Unused credits expire; monetary allowance never expands the 1000-hour quota.

## Tested rollback mechanics and live limitations

Synthetic tests verify webhook delete uses drop_pending_updates=false, ingress is stopped first, polling refuses remote webhook/dual-mode, and durable payment retry survives lost Core response/restart. They are not a performed live rollback.

1. Owner clicks **Отключить webhook** in `/admin`. This stops new acknowledgements and calls deleteWebhook(drop_pending_updates=false). Confirm registered=false. Stop Core webhook mode (TELEGRAM_DELIVERY_MODE=disabled) via authoritative config; this releases transport lease. Existing queued/review jobs and outbox remain in PostgreSQL. Do not delete tables or roll back money.
2. Ensure webhook actually absent and no active Core consumer/local poller. Set Bot mode polling and latch true, then `heroku ps:scale worker=1:Eco --app student-ai-bot-ernar-beta`. The worker itself rechecks remote webhook and holds shared lease. Temporarily keep Core web=1 for its bridge, or use an explicitly planned mutually exclusive transport. Two dynos consume <=2 h/hour; a 24h temporary overlap adds <=24 h to the one-web monthly baseline. End rollback before reserve is exhausted.
3. To return to webhook, stop worker FIRST (`heroku ps:scale worker=0:Eco --app student-ai-bot-ernar-beta`), disable latch, switch Bot mode webhook and Core mode webhook, acquire lease, register preserving pending updates. Leave user/payment state intact.

Do not claim a rollback handles interrupted acknowledged non-payment jobs automatically: the polling worker does not consume Core's new queue. They remain available for the webhook consumer/review after restoration. Already-accepted payments are still in the shared existing outbox and can be delivered by polling's retry loop.

No real Stars payment, owner login automation, secret transfer, new database/app/dyno subscription, provider migration or unrelated product work is part of this runbook.
