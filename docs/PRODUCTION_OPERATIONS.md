# Production operations

Production topology is one Eco Core web process, one Eco Bot worker after cutover,
and the shared Essential-0 PostgreSQL database. Do not add keepalive traffic: the
Core is expected to sleep after inactivity and use bounded client retries. Never
change cost, add resources, restore a database, or delete production data without
owner approval.

## Health and triage

- **Core unavailable:** check Heroku formation/release, `/api/health`, PostgreSQL
  status, and Sentry. Recycle the approved web process only after capturing the
  release and error state. Do not scale above one.
- **PostgreSQL unavailable:** stop write-producing operations, preserve outbox rows,
  inspect the add-on status, and wait for recovery. A restore is destructive and
  requires explicit owner approval.
- **Telegram polling conflict:** scale the cloud worker to zero first. Confirm no
  worker dynos, then check the PostgreSQL lease marker and local lock listener. Never
  run local and cloud polling together.
- **Payment stuck in outbox:** use the no-polling preflight to view aggregate pending
  and delivered counts. Check bridge/Sentry categories and Core health. Do not edit,
  delete, or manually replay payment rows; the retry loop and Core charge uniqueness
  are the recovery boundary.
- **Eco hours low:** keep the worker at one and allow the Core to sleep naturally.
  Do not create a keepalive or scale another dyno. Escalate a plan change to the
  owner before the shared Eco pool is exhausted.
- **Sentry alert:** triage by service, environment, release, and allowlisted category.
  Events must not contain tokens, cookies, request bodies, Telegram profiles,
  payment payloads, database URLs, or local variables.

## Rollback order

For a Bot incident, scale the cloud worker to zero and prove it stopped before
restoring the legacy bot. Preserve PostgreSQL and outbox data. For a Core release
incident, record the failing release and use Heroku release rollback only when its
schema compatibility is known. Recheck health, HTTPS, Sentry, and bridge behavior
after every rollback.

The production Telegram OIDC and owner-admin gate remains red until a fresh real
login verifies Telegram identity `8247777174`, admin access, logout/relogin, and
state/replay rejection. Offline synthetic tests are not a substitute for this gate.
