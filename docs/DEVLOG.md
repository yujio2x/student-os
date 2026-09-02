# Student OS engineering DEVLOG

## 2026-09-02 - Starting state and migration audit

### Repositories

- New local workspace: `C:\Users\ernar\Desktop\project2034\student-os`.
- New public remote: `https://github.com/yujio2x/student-os.git`.
- GitHub reported the new repository as empty with `main` as its default branch.
- Existing local bot: `C:\student-ai-bot`.
- Existing bot local HEAD: `5a9ce776a6e60a3879f51263443d9c89c115f7c1` (`Solve full tests from saved photos`).
- Existing bot GitHub repository: `yujio2x/student-ai-bot`; GitHub HEAD matches the local HEAD.
- Existing local bot remote still displays the former username `yujio-dev`; GitHub has redirected the repository to `yujio2x`. The old repository and history are not modified.
- Existing bot contains unrelated untracked image/output files. They are preserved and excluded from this migration.

### Existing stack

- Python 3.12, `python-telegram-bot`, OpenAI Responses API, SQLite, and `python-dotenv`.
- The Telegram bot is a live scheduled process and remains operational; Student OS does not start, stop, or modify it.
- The bot has meaningful tests for AI response completion, Telegram flows/helpers, payments, feedback, analytics, and photo sessions.

### Migration classification

| Area | Decision | Reason |
| --- | --- | --- |
| OpenAI Responses integration patterns | REFACTOR | Keep `store=False`, bounded continuation, token accounting, and explicit instructions; expose them behind a web/domain service. |
| Assignment response contract | REUSE + REFACTOR | Preserve analysis, solution/explanation, verification, and the highly valued defense guidance as first-class structured sections. |
| Defense follow-up prompt | REUSE | The 30-60 second first-person defense script is product-defining and UI-independent. |
| Image task extraction | DEFER | Valuable later, but text assignment is the v0.1 vertical-slice boundary. |
| Telegram handlers, Stars payments, referrals, admin/funnel UI | DEPRECATE for Student OS core | Telegram-specific and outside v0.1; the old bot remains untouched as a future adapter. |
| Existing bot SQLite schema | REPLACE | It models Telegram access/payment analytics, not schedules, assignments, deadlines, or user-owned web data. |
| Existing bot configuration | REFACTOR | Reuse environment-based secrets, but remove Telegram/payment settings from the web core. |

### Architecture and stack decision

Student OS starts as one Python web application: FastAPI API, SQLite via the Python standard library, a small domain/service layer, and a framework-free responsive web client. This keeps the existing Python/OpenAI knowledge, supports a future Telegram adapter, is inexpensive to deploy, and avoids a separate frontend build system during v0.1. The boundaries are `web/API -> application services -> domain/persistence/AI`.

No secrets or private bot data are copied. Only synthetic seed examples may enter Git.

### Current checkpoint

Git checkpoint:
commit: 54d119a
branch: main
pushed: YES
purpose: safe repository foundation and documented migration audit
tests: staged secret scan
attack checks: no obvious credential patterns in staged content
known limitations: feature implementation was not part of this initial commit

## 2026-09-02 - Working v0.1 vertical slice

### Implementation

- Added a FastAPI application with SQLite persistence and a framework-free responsive client.
- Added synthetic schedule seed data. No data from the live Telegram bot/database was copied.
- Added Today, Schedule, AI Study, and Calendar views as one visual product.
- Schedule supports week/day view and persisted visibility for room, teacher, lesson type, group, and notes.
- AI Study accepts text assignments up to 12,000 characters and returns analysis, explanation, approach, checks, "How to Defend", likely teacher questions, and pitfalls.
- Without `OPENAI_API_KEY`, a clearly labelled deterministic demo result keeps the entire product flow testable.
- With `OPENAI_API_KEY`, the Responses API uses `store=False` and a strict JSON schema. The schema prevents arbitrary response shape drift and treats `suggested_due_at` as nullable.
- AI deadline extraction is a suggestion only. The user reviews/edits title, subject, and date before an explicit save.
- Saved deadlines appear in both Today and Calendar and can be marked complete.
- Duplicate deadline submissions with the same user/title/time/source are idempotent.
- User-owned tables include `user_id` to avoid a future schema rewrite, but the current application intentionally uses one local demo user until authentication is designed.

### Changed files

- `app/config.py`: environment configuration.
- `app/database.py`: schema, synthetic seed, preferences, schedule, and deadline persistence.
- `app/ai_service.py`: migrated study/defense concepts, demo mode, live structured Responses integration.
- `app/main.py`: validated API and static client serving.
- `static/index.html`, `static/styles.css`, `static/app.js`: complete responsive UI and client flow.
- `tests/test_vertical_slice.py`: contract, persistence, boundaries, duplicate, and injection-shaped input checks.
- `.github/workflows/ci.yml`: Python 3.12 install, compile, and test CI.

### Tests and attack checks

- `python -m pytest tests -q`: 9 passed.
- First sandboxed run failed before test setup because Windows denied pytest's default temp directory. Running the same suite with normal local test permissions succeeded; this was an environment failure, not a product failure.
- Checked empty, whitespace-only, too-short, and 12,001-character assignment input.
- Checked malformed date, Unicode, emoji, and prompt-injection-shaped assignment content.
- Checked AI analysis does not save a deadline.
- Checked duplicate deadline submissions do not create duplicate rows.
- Checked unsupported and duplicate preference fields are rejected.
- Checked deadline update ownership boundary returns 404 for unavailable IDs.
- Browser flow verified: AI Study -> defense -> editable deadline -> save -> calendar -> completion toggle.
- Browser responsive QA at 390x844 exposed a horizontal overflow that moved schedule settings off-screen. Fixed with min-width containment and a mobile flex scroller; recheck showed body width exactly 390px.
- Browser console: no warnings or errors from Student OS.

### Security and privacy

- `.env`, SQLite runtime databases, uploads, logs, caches, and virtual environments are ignored.
- Staged files must be scanned before each public push.
- SQL uses parameterized statements. API inputs have bounded lengths and enum/pattern validation.
- The client renders user/AI content with `textContent`, not `innerHTML`, preventing obvious stored HTML/script execution.
- Live AI instructions explicitly treat assignment content as untrusted and preserve the response contract.
- No authentication exists yet; do not expose this checkpoint as a multi-user public service.

### Official OpenAI documentation check

- The configured `gpt-5.6-luna` model supports the Responses endpoint and Structured Outputs.
- Updated the live format from legacy JSON mode to strict `json_schema`, matching current official guidance.

### Known limitations

- Live API behavior was not exercised because no new credential was requested or copied; demo mode and schema construction are tested locally.
- Single local user only; user isolation is represented in persistence but not authenticated.
- Schedule rows are synthetic and read-only in the UI.
- No assignment history, deadline edit/delete UI, recurring events, notification system, file inputs, or PWA manifest/service worker.
- Calendar is a month grid, not a full timezone-aware calendaring engine.

### Git checkpoint

Git checkpoint:
commit: b8efbc65257a49aa2c7d6d44a98136b64b10c043
branch: main
pushed: YES
purpose: complete local Student OS v0.1 vertical slice with CI
tests: 9 passed; `python -m compileall -q app tests` passed
attack checks: input boundaries, Unicode, injection-shaped input, duplicate action, XSS rendering boundary, mobile overflow
known limitations: see section above

### Next technical step

Verify GitHub Actions, then add schedule/deadline editing and authentication before any public multi-user staging.
