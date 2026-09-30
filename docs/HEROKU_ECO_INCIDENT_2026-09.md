# September 2026 Eco incident

Status: forensic evidence collected 2026-09-30; webhook implementation locally tested (Core 177 passed/27 expected environment skips; Bot 109 tests/5 expected PostgreSQL skips). Bot CI including PostgreSQL passed for 93ef0de. Core PostgreSQL CI remains to be verified after push. Live deployment/cutover/cold-start QA are pending. No purchased resources, runtime restarts or real payments were used in the audit. Bot formation was subsequently set to 0:Eco to prevent October restart of the old topology.

## Impact and evidence

Student OS web and Telegram cloud bot stopped when the shared account Eco pool was exhausted. Dollar credits did not make more runtime hours available.

The authenticated Heroku Notifications page was read directly. It shows September 23 06:12, 80% of 1000 hours used, and September 28 06:10, the allocation exhausted and apps stopped until next month. These are notification delivery times, not precise metering boundaries. Local display is treated as Asia/Qyzylorda (UTC+5), consistent with CLI shutdown timestamps; this timezone assumption is explicit.

Authenticated account Billing on September 30 shows:

| App | September usage |
|---|---:|
| student-ai-bot-ernar-beta | 525.68 h |
| student-os-ernar-beta | 515.62 h |
| Account total | 1041.30 h |
| Remaining | 0.00 h |

The two app rows sum exactly to the dashboard total. `heroku apps --json` lists only these two owned personal Cedar apps (created September 4 at 09:03 UTC). `heroku pipelines --json` returns `[]`. Account add-ons list only postgresql-animate-45477, heroku-postgresql:essential-0, provisioned, billed 500 cents/month. There is no Scheduler, Redis, New Relic add-on or second database in that inventory.

`heroku ps` shows Core web=1:Eco, idle since September 28 06:11:20 +0500; Bot worker=1:Eco, idle since 06:13:03. No current one-off dynos. CLI app totals are 515h37m and 525h40m. Its quota line says -42h18m, implying 1042.30 h, one hour different from Billing. This unresolved reporting discrepancy is NOT evidence for an extra consumer. Use the dashboard total and preserve the discrepancy. The 41.30 h above the nominal limit are metering/cutoff overshoot as reported; a daily refresh and delayed warning cannot provide an exact 1000-hour cutoff. Do not assert an undocumented reason for the overshoot.

Bot release v18 enabled CLOUD_POLLING_ENABLED at 2026-09-06T03:21:27Z. DEVLOG's September 6 cutover records local polling stopped first, one Eco worker scaled up and CLOUD_POLLING_LEASE_ACQUIRED observed. Last Bot release is v19, b49ffc40, September 10; Core v36, a4d43dd7, September 15. Worker from latch time to final idle is 525.86 h; dashboard 525.68 h differs by about 11 minutes. This strongly supports effectively 24/7 worker operation, allowing deploy/start gaps and small one-off usage. It does not establish every second of historical formation.

## Required interval reconstruction

Use September 1 00:00 local as the baseline. This is a calendar baseline, not app launch time. Approximate thresholds assume notification usage equalled 800 and 1000 h; Heroku refreshes daily and messages lag, so these are estimates, not per-day metering data.

| Interval | Elapsed | Usage increment | Average concurrent Eco dynos |
|---|---:|---:|---:|
| Sep 1 00:00 to Sep 23 06:12 | 534.20 h | ~800 h | ~1.498 |
| Sep 23 06:12 to Sep 28 06:10 | 119.967 h | ~200 h | ~1.667 |

Assuming worker continuously active after Sep 6 08:21:27 local, first interval worker ~405.84 h and residual web/one-offs ~394.16 h. In the second interval worker ~119.97 h and residual web/one-offs ~80.03 h, or ~16 h/day. These estimates are consistent with one always-on worker plus a frequently awake web, but must not be substituted for the exact monthly app totals. The extra 41.30 h in the final dashboard cannot be allocated to either notification interval without historical metering.

Core 515.62 h is at least 90.8% of the 568.14 h between app creation and shutdown (actual first web deployment was later). Bot is effectively always-on, Core sleeps intermittently but substantially exceeds the intended 200 h/month. Full-month potential of two continuous dynos is 1440/1488 h, exceeding the pool by 440/488 h.

## Monitoring and historical limitations

Both repos' tracked app/scripts/workflow/docs were searched for Pingdom, Better Uptime, UptimeRobot, New Relic, cron, scheduled health/curl and keepalive patterns. Existing CI is push/PR based and its PostgreSQL health check targets a disposable CI database. No scheduled production HTTP ping was found. Sentry initializes content-free error reporting with automatic integrations disabled; this is not an uptime check.

A filtered Heroku source snapshot contains 1010 lines from Sep 26 12:40:26 UTC to Sep 30 08:18:10 UTC: 837 router records, 130 lifecycle/sleep matches. Classified routes: auth 10, product API 25, web/static/other 800; no health or bridge routes in that retained sample. There are repeated real idle/unidle transitions; sample startup after wake was about 5-13 seconds. This proves intermittent sleep and rules out an uninterrupted keepalive within that sample, not across September. It does not identify visitors or distinguish QA, crawlers and normal use. No raw URLs, IPs or request payloads are retained here.

One-offs for synthetic cloud preflight/payment persistence and monitoring were documented early in September. Per-app billing includes one-offs; exact historical one-off hours/process breakdown is unavailable in the current inventory and rolling logs. No evidence supports material runaway one-offs or another app. Deleted/transferred apps and externally owned monitoring services cannot be disproved solely from current inventory; two current app totals explain the entire displayed account usage. External service dashboards were not exhaustively audited. No service was disabled.

## Root cause and contributing factors

The production topology allowed two separately active Eco processes against one 1000-hour account pool. The worker consumed 525.68 h and Core 515.62 h, exhausting the pool. This is an architecture capacity failure, not an attribution to unexpected traffic.

CLOUD_COSTS already recognized 720-744 h for a full-month worker and proposed <=200 h Core. That was a usage target without enforcement or a worst-case proof. Dollar budgeting ($5 Eco + $5 database against $13 credits) was correct under eligibility, but runtime budgeting depended on Core sleeping enough. An 80% warning came with only approximately five days before shutdown; the warning was not a consumption forecast or an automatic corrective action.

## Selected permanent correction (implemented, live verification pending)

Prepared code: one Core web.1:Eco accepts authenticated Telegram webhooks, persists updates to the existing PostgreSQL, and runs one bounded consumer in its own process. Successful payments enter the existing bot_outbox payment journal before HTTP acknowledgement. Target: Bot worker=0, polling disabled, no other Eco formations/review apps/schedulers. Current worker formation is zero; authoritative polling config still requires its cutover update. Reuse the small Bot transport adapter as a pinned vendored library; do not import the legacy bot, its local ledger or AI engine into Core. Core retains product/identity/entitlement ownership. See [precise processing guarantees and rollback](HEROKU_WEBHOOK_RUNBOOK.md).

Worst-case recurring runtime is 30*24=720 or 31*24=744 h; headroom 280/256 h. This proof assumes no second Eco process. One-offs, deployment overlap, temporary rollback and future apps must be budgeted separately inside the headroom and audited; it is not an account-wide guarantee against arbitrary future operator actions. No keepalive is needed for the hours proof. Heavy AI cannot run in a Telegram request because the existing transport allows 45 s and Heroku has a 30 s initial response window.

Resources remain $10/month, $13 monthly student allowance, expected $0 cash while eligible and with no other charges/taxes. Student credits expire monthly and are distinct from Eco capacity.

## Official documentation checked September 30

- [Eco rules, wake, daily metering, worker and one-off usage](https://devcenter.heroku.com/articles/eco-dyno-hours)
- [Heroku routing timeouts](https://devcenter.heroku.com/articles/http-routing)
- [Telegram setWebhook, retries, authentication and getUpdates exclusion](https://core.telegram.org/bots/api#setwebhook)
- [Telegram updates retained at most 24 hours](https://core.telegram.org/bots/api#getting-updates)
- [Pre-checkout 10-second deadline](https://core.telegram.org/bots/api#answerprecheckoutquery)
- [Student monthly credits](https://help.heroku.com/Z3RHNRHD/how-does-the-heroku-for-github-students-program-work)
- [Pricing](https://www.heroku.com/pricing/)

Telegram retries non-2xx but documents no precise retry schedule or webhook timeout SLA; do not invent either. Eco wakes on inbound traffic when hours remain, but cannot guarantee the 10-second checkout deadline. A cold checkout must fail closed; a paid update must remain durable. Updates stranded at Telegram during the September outage may already have expired after 24 h; new architecture cannot recover those. Payment reconciliation may therefore require provider evidence/owner action, without claiming no September payment loss.

## Cutover and rollback gate

Do not automatically restart the old worker at October renewal. Before renewal, scale Bot worker to zero once; this does not spend new hours. Prepare tested releases/config while exhausted without running one-offs or repeated starts. Owner manually creates TELEGRAM_WEBHOOK_SECRET in the existing Core Doppler config; never print or move its value. Runtime registration reads it only inside the production process, not via automation interfaces.

Cutover after pool reset confirmed in Billing (October 1; exact reset hour not established): stop and confirm all pollers FIRST, disable CLOUD_POLLING_ENABLED via its authoritative sync, deploy tested webhook-ready releases, enable Core webhook mode, verify health/database/runtime lease, register webhook with drop_pending_updates=false, verify redacted webhook status, manually smoke /start, /balance, text/photo/feedback and /buy without a real payment, then inspect account formations and usage. Never register before stopping polling. Do not drop pending updates.

Rollback: stop webhook processing, delete webhook with drop_pending_updates=false, verify absent, then disable Core webhook mode/release lease; restore exactly one polling worker with explicit latch and shared lease, preserve PostgreSQL journals. Keep rollback short: two active processes cost up to 2 h/hour; a 24-hour overlap adds <=24 h above the one-web baseline. Synthetic tests cover delete preserving updates, dual-mode refusal, ownership recovery and payment restart/ambiguous response. A live rollback/cutover is not yet performed.

Deployment preparation was attempted only after Bot tests/CI passed and worker formation=0 was confirmed. Automatic approval review rejected the Heroku git deployment as a premature production deploy before renewed quota/secret/cutover. No deployment command ran, no release was created. Do not bypass that decision. The code and exact commits must be reviewable before any owner approval request.

## Audit privacy limitation

No config values/.env were requested. Historical release listing unexpectedly exposed a credential-shaped config-key label from an older known remediation. It is not reproduced or saved in these docs. Further metadata inspection uses safe field projections. The audit cannot honestly claim zero incidental exposure in tool output.
