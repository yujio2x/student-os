# Student AI shared-engine architecture

## Audited source

The live predecessor was reviewed read-only at `C:\student-ai-bot`, HEAD `5a9ce776a6e60a3879f51263443d9c89c115f7c1`. That worktree already contains unrelated edits in `app/bot.py` and untracked image/output files. This sprint did not modify, stage, commit, import, or write to that repository or its database.

The useful product behavior is not the Telegram handler layer. It is the combination of a bounded Responses API runner, task/photo domain flows, usage accounting, entitlement lifecycle, and the first-class defense explanation.

## Target mapping

| Old bot responsibility | Reusable domain/service | Telegram adapter | Student OS web |
| --- | --- | --- | --- |
| `AIService._complete_answer` | bounded Responses runner, usage result, `store=False` | sends formatted Markdown chunks | renders structured sections in the right pane |
| `AIService.answer` | text-task analysis | reads Telegram message | reads subject/title/assignment form |
| `extract_image_tasks` | image recognition producing a bounded recognized-task set | downloads Telegram photo | future validated image upload |
| `answer_photo_session` | request against recognized text + bounded previous selection | uses 24-hour Telegram session | future web photo session, without retaining raw image |
| `defense_explanation` | defense capability over task + answer | callback button | first-class `Как защитить`, questions, and pitfalls sections |
| `claim_*` / `restore_access` | reserve → commit/release entitlement semantics | Telegram identity adapter | verified internal user + linked Telegram identity |
| `log_request` token fields | request usage record | operational bot analytics | token counts on committed reservation |
| `bot.py` handlers/keyboards | none | remains Telegram-only presentation | never imported or called by web core |

Student OS now exercises the shared direction in production code: verified identity gate → connected entitlement → idempotent reservation → bounded structured engine call → token-accounted commit, with release on engine failure. Schedule, Calendar, Deadlines, Settings, and export never enter this path.

## Web information architecture

The left pane owns input and state: subject, title, assignment text, future photo/file boundary, Telegram status, and honest entitlement state. The right pane owns durable comprehension: task understanding, explanation/solution, approach, checks, `Как защитить`, likely teacher questions, pitfalls, feedback, and an explicitly confirmed deadline.

This intentionally does not mirror a long Telegram message. The JSON Schema is a web presentation contract and keeps every defense-related section addressable.

## Photo compatibility boundary

Before enabling the currently disabled photo/file input, add a service contract with three operations:

1. Validate MIME, signature, decoded dimensions, and a bounded byte size before any AI call.
2. Recognize all visible tasks once and store only normalized recognized text for at most 24 hours; raw images are not retained by default.
3. Answer a selected task/range using recognized text and the previous bounded selection, without charging the photo setup twice.

The old bot charges five paid credits for a photo setup and permits follow-ups inside its session. Student OS must not assume that pricing. The authoritative ledger adapter must return a quoted charge and idempotency key before the web UI asks for explicit confirmation.

Compatibility fixtures must cover a single task, numbered multi-task photo, generic “solve all”, explicit range, unreadable fragment, 24-hour expiry, repeated confirmation, concurrent confirmation, follow-up without a second charge, failure refund, and `Как защитить` over the selected answer.

## Ledger migration and rollout

1. Freeze contract fixtures from sanitized old-bot text/photo answers, token usage, trial, paid, unlimited, failure, and duplicate-update cases.
2. Extract the engine runner/domain behind interfaces while the Telegram bot still uses its existing implementation. Compare outputs in tests; do not share Telegram handlers.
3. Expose one authoritative entitlement adapter keyed by verified Telegram identity and request ID. Never let two processes independently write the live SQLite ledger.
4. Reconcile a staging copy: identities, balances, unlimited flags, trials, payments, reservations, refunds, and token totals. Mismatch blocks rollout.
5. Enable Student OS for a small allowlist, then move the Telegram bot onto the same service semantics only after observability and rollback checks pass.

Rollback is configuration-first: disable the web engine/ledger adapter, reject new Student AI calls with an honest unavailable state, drain or release pending reservations, and keep organizational features available. Never roll back by restoring an old database over the live file. Keep the old bot on its previous adapter until reconciliation is complete.

## Manual prerequisites and blockers

- Production Telegram client/bot credentials, allowed domain/redirect, and a verified account recovery decision.
- Read-only staging copy of the live ledger plus an approved maintenance/migration window.
- Product decision for shared trial and web photo pricing; these cannot be inferred safely from Telegram UI behavior.
- An authenticated service boundary between adapters and the ledger, with request signing, timeouts, audit logs, and rate limits.
- Device QA with real sanitized tasks before enabling the photo input or public beta.

No live migration or paid AI request is authorized by this document.
