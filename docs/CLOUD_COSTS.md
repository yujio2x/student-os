# Heroku beta budget — verified 2026-09-04

Selected: Option A, two **personal Cedar** apps in Europe, shared Eco subscription.

| Resource | Plan | Monthly maximum |
|---|---|---:|
| Core web + separate worker-only bot app | Shared Eco pool | $5 |
| One shared PostgreSQL database | Essential-0 | $5 |
| Total target | | $10 |

Dashboard showed $312 Platform Credits and $0 current usage before subscription.
Owner approved Eco terms at action time. Subscription succeeded: $5/month,
1000 hours remaining, 0 hours used. This is a recurring subscription, not a deployment.
After separate owner approval of the database order terms, Essential-0 was provisioned:
`postgresql-animate-45477`, attached to `student-os-ernar-beta` as Heroku-managed DATABASE.
Its confirmed price is $5/month and state is created. No cloud bot polling has started.

Student credits cover **up to $13 each month**, not an unrestricted $312 wallet.
Unused monthly allowance expires; the program lasts 24 months. Expected cash cost
for the selected $10 topology is $0 while eligible monthly credits remain and no
other billable services consume that allowance. Taxes/account adjustments, if any,
must be checked in the account invoice; do not promise an unconditional zero bill.
Do not divide $312 by $10 to estimate runway.

Worker-only Eco app does not idle-sleep. One continuous worker uses 720–744 hours
in a 30–31-day month, leaving 256–280 hours for Core and one-off dynos. Target Core
awake time <=200 hours/month, leaving 56–80 hours reserve. Requests from Telegram
bridge and the 30-minute idle tail also count. No keepalive pings. Empty payment
outbox makes no Core requests; pending retries and traffic can keep Core awake.
At pool exhaustion **both apps stop until the next month**, not just the web app.
Monitor hours without HTTP-pinging Core. Heroku's 80% email warning is not a forecast.

Cold starts can exceed the bot catalog's five-second timeout. Pre-checkout fails
closed; already-paid events must remain in PostgreSQL outbox until delivered.
Local SQLite outbox is not acceptable on Heroku. Cutover is blocked until migration,
restart persistence, cold-start and payment failure tests pass.

Alternatives: Basic Core + Eco bot + DB = $17 (expected $4 cash/month);
Basic + Basic + DB = $19 (expected $6 cash/month). Neither is authorized.

Created empty apps (no deployed process types):
- `student-os-ernar-beta`, Cedar/heroku-24, eu.
- `student-ai-bot-ernar-beta`, Cedar/heroku-24, eu.

Sources:
- https://devcenter.heroku.com/articles/eco-dyno-hours
- https://www.heroku.com/pricing/
- https://help.heroku.com/Z3RHNRHD/how-does-the-heroku-for-github-students-program-work

No additional paid resource without verifying its actual plan and budget coverage.
