# Cloud readiness — 2026-09-04, owner away

## Invariants

Doppler CLI login is BLOCKED_BY_OWNER. Do not retry login, extract browser sessions,
request tokens in chat or change either existing In Sync integration. No config-var
writes in this checkpoint; DATABASE_URL stays entirely Heroku managed. No paid
resources, cloud polling, live bot restart or cutover. Existing Windows bot stays live.

## Build and configuration boundary

Both repositories pin Python 3.12; slug exclusions keep local environments, databases,
logs and tests out of runtime artifacts. Core uses app.cloud_web:application with
Uvicorn access logging disabled. Bot uses app.cloud_worker, not legacy app.bot: the
cloud entry point only installs the Core bridge and PostgreSQL outbox, never legacy
SQLite/AI services. It refuses to poll unless CLOUD_POLLING_ENABLED=true; leave it
unset/false AND worker=0 until a separately approved cutover.

`python -m app.cloud_preflight` in each repository reads environment only, not .env.
It prints names of missing/invalid settings, never values. Exit 0 means config shape
ready, NOT successful connectivity/migration/OIDC or permission to start polling.
Run it inside the later configured runtime. Running locally without cloud env should
fail; do not copy production secrets into local files merely to make it pass.

Required Doppler settings after owner login:

| Core stg | Bot stg |
|---|---|
| APP_ENV=staging, DEV_LOGIN_ENABLED=false, DEV_ADMIN_ENABLED=false | STUDENT_OS_BRIDGE_ENABLED=true |
| ENTITLEMENT_SOURCE=core | CLOUD_POLLING_ENABLED=false |
| OPENAI_API_KEY, existing allowed model settings | No OpenAI key needed in bridge mode |
| BOT_BRIDGE_SECRET, TELEGRAM_BOT_TOKEN | STUDENT_OS_BRIDGE_SECRET, TELEGRAM_BOT_TOKEN |
| TELEGRAM_CLIENT_ID, TELEGRAM_CLIENT_SECRET, TELEGRAM_REDIRECT_URI | STUDENT_OS_API_URL=verified Core HTTPS origin |
| Optional SENTRY_DSN | Optional SENTRY_DSN |

Generate a fresh >=256-bit bridge secret in memory and store the same value under
the two respective bridge-key names. Migrate allowlisted existing credentials only;
never an entire .env, DATABASE_URL, DOPPLER_* or Heroku/add-on-managed values.
Absent Telegram OIDC credentials require official owner/BotFather flow, not invention.

## Eco and payment correctness

Background durable-outbox retry now uses persisted last_attempt_at/attempts and delays
1, 2, 4, 8, 16, 32 then 60 minutes, capped at 60. Empty queues make no Core requests.
Single HTTP calls/batches remain bounded, and transient outages stop the batch. Paid
pending entries are never discarded because a retry budget expires. Retrying uses the
same charge ID; Core commit/idempotency remains the exactly-once credit boundary.
No auto-resubmission of non-idempotent AI requests; first cold-start request may fail
and invite user retry. Real cold-start latency is still unmeasured until deployment.
Many pending entries can still keep Core awake: backoff is not a dyno-hours guarantee.

## Domain / ACM preparation

Free ACM enabled on student-os-ernar-beta. student-os.dev added, pending DNS.
Actual Heroku target: triangular-quince-o3z6hou8rvdwxkc3dcna64jv.herokudns.com.
DNS unchanged deliberately: do not direct users to an unconfigured deployment.
Once Core is healthy, use an apex ALIAS/ANAME/flattened CNAME supported by the DNS
provider, not a guessed IP and not the herokuapp.com hostname. Preserve MX/TXT and
unrelated records. If current provider cannot alias apex, stop for an explicit DNS
provider/domain strategy; do not add paid DNS or silently move nameservers.
Then verify DNS, ACM issued status and HTTPS chain before registering the exact OIDC
callback https://student-os.dev/api/auth/telegram/callback. No certificate claim yet.

Old Heroku CLI 7.53.0 omitted required sni_endpoint. The bounded preparation script
uses the existing authenticated Heroku CLI session and official API with null SNI;
it never attempts Doppler auth or emits credentials. No manual certificate purchase.
Sources: [required SNI field](https://devcenter.heroku.com/changelog-items/1938),
[Eco ACM](https://www.heroku.com/blog/automatic-certificate-management-for-eco-dynos/).

## Sentry boundary

Unset SENTRY_DSN means disabled. Only allowlisted operational category + event ID are
sent; the before-send hook reconstructs the event from scratch. Default integrations,
PII, stack/local/source capture, breadcrumbs, sessions and tracing are disabled. No
user IDs, assignments, images, cookies, auth headers, payment payloads or exceptions
are sent. Core reports a generic unhandled category; bot reports retry-loop failures.
Real SDK tests use an in-memory transport and hostile content, not a live Sentry DSN.
This is intentionally coarse error visibility, not full distributed tracing.
Real Sentry project/DSN and synthetic dashboard delivery remain external acceptance;
the code does not claim to sanitize unrelated platform/server logs.

## HTTPS / BrowserStack acceptance prepared, not executed

Use synthetic disposable staging accounts only; no private homework or real payments.

| Surface | Required result / evidence |
|---|---|
| Android Chrome 390x844, desktop Chrome 1440x900 | Login, Today/Calendar deadline edit, import preview stays editable; screenshots have no overflow |
| iOS Safari or second browser | Login/callback, settings order, responsive modal and keyboard; record real browser/device versions |
| HTTPS and restart | Valid domain/certificate, Secure cookies, callback no-store/no-referrer, signed readiness healthy, data persists through Core restart |
| Public shell / offline | Root sw.js served JS, no private API/auth/admin caches; offline shell not presented as live data; actual standalone install separately verified |
| Synthetic bridge/outbox | Cold Core timeout leaves paid record pending; restart/retry credits once, tampered signature/receipt rejected, no duplicate AI submit |

BrowserStack execution needs a working HTTPS deployment and an authorized account.
No subscription, access-key harvesting or mocked screenshot accepted as device QA.
Existing local UI is unchanged in this checkpoint; cloud browser QA remains blocked.

## Ordered deployment / rollback gate

1. Owner completes scoped Doppler login; direct in-memory secret migration, validate
   only presence and sync success. Preflight both runtimes, worker=0/latch=false.
2. Build/deploy tested commits. Worker-only process types do not auto-start on Heroku;
   verify formation=0 after bot deployment. Core first web deployment may auto-start:
   do not deploy Core before required configuration and storage readiness are present.
3. Core startup applies checksummed transactional migrations; check signed readiness,
   create synthetic record, restart Core and verify persistence. Never alter applied
   migration files or downgrade/drop data. Finish domain/ACM/OIDC and matrix above.
4. Only after owner authorizes cutover: backup local state/outbox, stop local polling,
   explicitly enable cloud latch and exactly one Eco worker. Never run both pollers.
5. Rollback: stop cloud worker FIRST, preserve pending PostgreSQL outbox and reconcile
   charges, restore prior compatible code/local runtime. Do not destroy/reset database
   or assume code rollback reverses schema. Never enable legacy paid flow with an
   unreconciled Core outbox. Leave paid delivery pending if safe recovery needs owner.

[Heroku formation defaults](https://devcenter.heroku.com/articles/dyno-formation).

## Exact next owner action

In PowerShell at home (do not paste resulting codes/tokens into chat):

```powershell
& "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Doppler.doppler_Microsoft.Winget.Source_8wekyb3d8bbwe\doppler.exe" login --scope "C:\Users\ernar\Desktop\project2034\student-os"
```

Choose Student OS workspace. Immediately after login: allowlisted local credentials
and fresh shared bridge secret -> the existing two stg configs, then preflight/Core
deployment with bot worker still 0. OIDC/Sentry credentials not yet created remain
their own external gates; successful CLI login does not create those credentials.
