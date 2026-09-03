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

Update 2026-09-04: the boundary below is now implemented in `PhotoService` and both
adapters. Quotes bind the current source; setup uses one shared trial or five credits.
The canonical engine recognizes bounded task arrays, then uses the existing structured
analysis/defense contract for selections. Raw images are not persisted. Normalized text
expires at 24 hours; periodic cleanup removes expired rows. This supersedes the earlier
pricing blocker and disabled-photo status, not the need for live OCR acceptance QA.

Before enabling the currently disabled photo/file input, add a service contract with three operations:

1. Validate MIME, signature, decoded dimensions, and a bounded byte size before any AI call.
2. Recognize all visible tasks once and store only normalized recognized text for at most 24 hours; raw images are not retained by default.
3. Answer a selected task/range using recognized text and the previous bounded selection, without charging the photo setup twice.

The old bot charges five paid credits for a photo setup and permits follow-ups inside its session. Student OS must not assume that pricing. The authoritative ledger adapter must return a quoted charge and idempotency key before the web UI asks for explicit confirmation.

Compatibility fixtures must cover a single task, numbered multi-task photo, generic “solve all”, explicit range, unreadable fragment, 24-hour expiry, repeated confirmation, concurrent confirmation, follow-up without a second charge, failure refund, and `Как защитить` over the selected answer.

## Unified ledger and rollout

1. Student OS Core owns the new ledger from a clean state; the legacy bot database remains an untouched archive/rollback reference.
2. Web calls the canonical engine directly through the Core application service. Telegram calls the same semantic operation through the signed bridge; neither interface owns a second prompt contract.
3. Every request is keyed by internal user plus idempotent request ID and follows reserve → engine → commit/release.
4. Telegram Stars are delivered through a durable bot outbox and credited once by charge ID against the Core-owned catalog.
5. Enable the default-off Telegram adapter only after cross-project identity, trial, payment, AI, outage, and rollback tests pass.

Rollback is configuration-first: set the bot bridge flag to false and restart the bot. Its legacy path/database remain intact until the owner deliberately retires them. Never restore an old database over the Student OS Core ledger.

## Manual prerequisites and blockers

- Production Telegram client/bot credentials, allowed domain/redirect, and a verified account recovery decision.
- A persistent-volume Student OS database and a long random `BOT_BRIDGE_SECRET` shared through secret storage.
- Photo pricing is implemented as decided: one shared trial or five paid credits for setup; live OCR quality still needs acceptance.
- A reachable HTTPS Core URL for the bot host and a manual cutover window.
- Device QA with real sanitized tasks before public beta; fixture-based Web/photo QA is complete.

No live migration or paid AI request is authorized by this document.
