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
- GitHub Actions CI completed successfully for both the feature commit (`b8efbc6`, 23s) and checkpoint-record commit (`e88c5c3`, 20s).

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

Add schedule/deadline editing and authentication before any public multi-user staging.

## 2026-09-02 - UI/UX refinement sprint

### Product changes

- Renamed all visible `AI Study` labels to `Student AI` while preserving internal route/code names.
- Removed the temporary `S` avatar from the Student OS wordmark.
- Replaced the sparkle-like Student AI icon with a neutral outlined `AI` badge that does not imitate another product identity.
- Translated the remaining visible `Assignment -> understanding -> defense` copy to `Задание -> понимание -> защита` and reviewed the static client for other unintended English UI.
- Rebuilt schedule-field options as consistent rows with text on the left and checkboxes on the right.
- Translated the root `README.md` into Russian and updated it to describe the refined mobile behavior honestly.

### Mobile changes

- Increased bottom navigation height to 78px, each tab target to 60px, icon size to 25px, and label size to 12px; active state is more prominent.
- Replaced the horizontal mobile schedule with a vertical day-first layout.
- Mobile defaults to today's lessons. Optional week view renders five full-width vertical day sections, suitable for one long screenshot.
- Desktop and mobile view preferences are now independent: `schedule_view` defaults to `week`, while `mobile_schedule_view` defaults to `day`.
- Added a safe SQLite migration for existing `preferences` tables missing `mobile_schedule_view`.
- Reworked the mobile month grid to seven fluid columns inside the viewport. On narrow screens, events become compact accessible dots with their full title retained as the button title.

### Telegram architecture direction

- Added `docs/TELEGRAM_INTEGRATION.md` as the implementation boundary for Telegram login, Student AI-only credits, and future cloud backup.
- Student OS keeps its own stable user identity; Telegram ID is an external account link rather than the system-wide primary key.
- Credits are isolated behind a future Student AI entitlement service and do not gate Schedule, Calendar, Deadlines, or organizational features.
- Existing `user_id` ownership columns are retained as minimal groundwork; production auth/session code is intentionally deferred.

### Verification

- Automated suite: 12 passed, including visible-label and existing-database migration regressions.
- Python compilation passed.
- Desktop browser QA confirmed renamed navigation, removed avatar, neutral icon, and aligned checkbox rows.
- Mobile browser QA at 390x844: body width stayed within viewport, day view was selected, one day column rendered, schedule width was 358px, bottom nav was 78px, and each tap target was 60px.
- Mobile calendar QA at 390px: calendar and header were both 358px wide; each of seven cells was about 50.86px wide with no page overflow.
- Mobile optional week view rendered all five day columns vertically at the same x-position and width.
- Browser console contained no Student OS warnings or errors.
- GitHub Actions completed successfully for the UX feature commit (`15acd44`, 25s) and its checkpoint-record commit (`5edb471`, 21s).

### Git checkpoint

Git checkpoint:
commit: 15acd443a19affa51fb4850b8494c6783aaa50b5
branch: main
pushed: YES
purpose: product-directed UI/UX refinement, Russian README, and Telegram integration architecture
tests: 12 passed; `python -m compileall -q app tests` passed
attack checks: existing-database migration, viewport containment, separate device preferences, visible-label regression
known limitations: Telegram login, credits adapter, and cloud sync remain documented architecture, not implemented auth

### Next technical step

Continue with schedule/deadline editing or begin the reviewed Telegram session foundation before any public multi-user staging.

## 2026-09-02 - Schedule Management, Import, Navigation, Settings

### Product result

- Schedule now supports create, edit, and delete on desktop and mobile. Deletion requires an explicit browser confirmation.
- Every lesson field is editable and persisted: weekday, subject, start/end time, room, teacher, lesson type, group, and notes.
- Overlapping lessons are rejected with a readable conflict message. Updates exclude their own row from conflict detection.
- Schedule import is a two-step transaction: temporary recognition and editable preview first, explicit atomic confirmation second. Preview never writes lessons.
- Preview rows expose every lesson field and allow users to correct, remove, and add rows before confirming.
- Supported uploads are digital PDF, PNG, JPG, and JPEG up to 6 MB. Extension and file signatures are checked. Empty, oversized, encrypted, malformed, and textless PDFs fail without changing the schedule.
- Digital PDFs use local text extraction plus a bounded parser when no API key exists. Images use the structured OpenAI vision path when a key exists. Scanned PDF OCR is deliberately deferred; the UI tells the user to export it as PNG/JPG.
- The old `student-ai-bot` was used only as an architectural reference for Responses API safety patterns. Its code, database, process, and repository were not modified.
- Desktop gained a persistent collapsible sidebar. Mobile gained a hamburger drawer while retaining the four daily bottom tabs.
- Added Today, Schedule, Student AI, Calendar, Contacts, Knowledge Base, and Settings navigation destinations. Unfinished destinations are visibly marked `Скоро`.
- Settings now persist theme, displayed lesson fields, desktop default schedule view, and mobile default schedule view. Telegram, shared credits, cloud backup, export, and clearing remain honest future states.
- Updated `README.md` in Russian with the current feature and import contracts.

### Implementation boundaries

- `app/database.py`: owned lesson CRUD, overlap checks, and atomic reviewed import.
- `app/schedule_import.py`: bounded upload validation, digital PDF extraction, fallback parser, and strict structured image/text recognition.
- `app/main.py`: validated lesson and import models plus CRUD, preview, and confirmation endpoints.
- `static/index.html`, `static/styles.css`, `static/app.js`: responsive application shell, dialogs, editable import preview, CRUD flow, and settings.
- `tests/test_schedule_management.py`: persistence, validation, conflict, no-auto-save import, atomicity, malformed upload, size boundary, and Unicode coverage.

### Verification and attack pass

- Automated suite: 23 passed; only the existing Starlette/httpx deprecation warning remains.
- Python compilation passed. Bundled Node.js syntax validation of `static/app.js` passed.
- Pytest's default sandbox temp directory became unreadable due to the managed Windows ACL. The identical suite passed outside that sandbox with a dedicated temp path; this is an execution-environment issue, not a product failure.
- Checked invalid weekday/time order, blank subject, Unicode, overlapping existing rows, overlapping import rows, malformed signatures, encrypted/empty/textless PDF paths, upload size boundary, unsupported extensions, and prompt-shaped document content boundaries.
- Confirmed preview responses declare `saved: false`; database counts remain unchanged before confirmation; a failed multi-row confirmation writes zero rows.
- Client renders recognized values through DOM `textContent`/form values and never through `innerHTML`.
- Browser desktop QA at 1440x1000: sidebar, schedule, complete edit dialog, unchanged update round trip, import dialog, and settings all worked with no console warnings/errors.
- Browser mobile QA at 390x844: hamburger drawer, bottom navigation, settings, day-first schedule, dialogs, and tap targets fit without horizontal overflow. One checkbox alignment defect found during QA was fixed and rechecked.

### Known limitations

- This remains a single local demo user with no authenticated session boundary.
- Live paid OpenAI recognition was not exercised because no credential was requested or copied.
- Scanned PDF OCR, recurring schedules, import deduplication/merge strategies, deadline editing, notifications, Telegram login/credits, and cloud sync remain future work.

### Git checkpoint

Git checkpoint:
commit: pending
branch: main
pushed: pending
purpose: complete schedule CRUD, reviewed import, responsive application navigation, and persistent settings
tests: 23 passed; Python compilation and JavaScript syntax checks passed
attack checks: validation bounds, overlap atomicity, malformed files, no-auto-save, Unicode, XSS rendering boundary, mobile containment
known limitations: see section above
