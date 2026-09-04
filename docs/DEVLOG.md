# Student OS engineering DEVLOG

## 2026-09-04 — Option A subscription and empty Heroku apps

Owner selected Eco Web + separate worker-only Eco bot + Essential-0, $10/month
target, no Basic upgrade. Verified official prices and monthly credit limit ($13,
not an unrestricted $312 balance). Dashboard initially showed $312 credits and $0
usage. After explicit action-time acceptance of Eco terms, subscription succeeded:
1000 hours available, 0 used, $5/month recurring plan. See CLOUD_COSTS.md for limits.

Created empty personal Cedar/heroku-24 applications in Europe using the authenticated
Heroku CLI: `student-os-ernar-beta` and `student-ai-bot-ernar-beta`.
No code deployed, no dyno process types/polling launched, no database provisioned.
Core remote HEAD matched `c41b665`; bot local HEAD `f6e4552`, original dirty files intact.
CLI creation added Heroku Git remotes only; origin remains unchanged.

Postgres Essential-0 is $5/month in CLI, Marketplace and dashboard order form.
The final order form introduces acceptance of the add-on provider terms and Salesforce
MSA. It has NOT been submitted: action-time confirmation remains necessary for that
separate order. No credentials read/copied, no Doppler config or DNS changes.

Code audit: Core directly uses SQLite across database/entitlement/photo/OIDC/restore
services; cloud persistence is not implemented yet. Local PostgreSQL/Docker binaries
were not found at checked standard locations. Proposed next implementation: explicit
psycopg repository adapter, versioned transactional schema, bounded connections and
PostgreSQL concurrency tests before deployment. Never deploy current SQLite backend
as cloud persistence. Existing local bot remains untouched and running as before.

Validation for this checkpoint: documentation-only diff check; no application code
changed, no new runtime test result claimed. CI will execute the existing suite on push.
Exact next action: confirm Essential-0 order terms, provision only the selected $5 plan,
then implement/test PostgreSQL Core and outbox while cloud bot remains undeployed/off.

## 2026-09-04 — PWA eligibility and final beta handoff

Starting checkpoint `a4e48fd` (Core CI GREEN); bot remains `f6e4552` (CI GREEN).
Browser investigation found the old `/static/sw.js` registration could not control
the application root. Added `/sw.js` with no-cache, explicit root scope and migration
of only the exact obsolete Student OS registration. Cache cleanup now targets only
Student OS caches. Offline fallback normalizes asset query versions; API/admin/auth
callback data remain outside the public-shell allowlist.

Added an install action in Settings/Data only after `beforeinstallprompt` eligibility;
hidden when installed/standalone, no automatic prompt, no repeated submission.
Browser caught restore's fragile last-child selector after inserting the action;
fixed lookup/fallback and bumped script versions to invalidate stale browser assets.
Chrome now shows the install button, and restore opens/cancels correctly. Desktop
and 390×844 Settings checked; scrollWidth/clientWidth both 375 on mobile.
No actual OS installation was performed: eligibility is verified, standalone launch
and platform installation remain manual acceptance items.

Validation: full Core **99 passed** with actual pinned bot adapter, bot previous full
suite **73 passed** unchanged. New Node behavioral test covers eligibility, duplicate
click, dismiss, installed/standalone state, root registration and selective migration;
it runs in CI. Python compile, all JS syntax and diff checks pass. Final commit's CI
must be observed before declaring handoff green.

Autonomous implementation is handed off as a tested beta candidate, not a live release.
Shared identity/ledger/trial/credits/unlimited/payment and text/defense/photo flows are
covered by deterministic integration tests. Owner admin access, user listing, credit,
trial, unlimited, payment/feedback metrics and audit use the same Core data.
OIDC connection/logout, purchase handoff, photo sessions and owned-data restore exist.
Real Telegram authorization, paid AI/OCR quality and Stars delivery are NOT live-tested.

Exact next step: owner chooses the staging HTTPS origin and persistent-volume target;
follow `docs/DEPLOYMENT.md` with bridge OFF, then configure BotFather callback and secret
storage outside Git. Approve any live bot restart/payment/deploy separately. No production
action can safely substitute for these missing choices/credentials.
Later hardening: audited crash-reservation recovery policy and conversational photo
follow-ups beyond the implemented explicit selections. Neither is silently enabled.
Live safety remains NO for runtime restart, live bridge enablement, legacy DB writes,
secret exposure and production deployment. Bot's pre-existing dirty files remain untouched.

## 2026-09-04 — Synchronized bridge operational checkpoint

Resumed the paused work from Core `2e6eff5` / bot `5a9ce77`; current baseline
before this checkpoint is Core `36756a6` / bot `f6e4552`, both GitHub CI GREEN.
Completed signed v2 transport, durable Stars outbox, shared text/photo adapters,
OIDC account flow, atomic owned-data restore and cross-project integration harness.
This checkpoint adds shared idempotent feedback, signed health coverage and a
concurrent Web/bot trial regression. CI pins bot `f6e4552` exactly.

Bot operational hardening: stop an outage retry batch after the first transient
failure, cap payment delivery timeout, and never initialize legacy AI in bridge mode.
One Windows-only config test failed because clearing environment removed SSL platform
state. The shell mistakenly proceeded to commit `46d28a4` after that failure; follow-up
`f6e4552` isolates the config fixture, then the full suite passed. No live runtime changed.

Validation: Core **99 passed** including five actual-adapter integration tests;
bot **73 passed**. Python compile, every static JS syntax check and diff check pass.
Attack coverage includes duplicate/concurrent trial and payments, signature endpoint
binding/replay, foreign sessions, CSRF, refund paths, malformed/oversized uploads,
restore snapshot conflicts and SQL rollback. Starlette emits one nonblocking
httpx TestClient deprecation warning.

Browser QA: desktop Today/Schedule/AI/Calendar/Settings and admin overview render;
Settings retains requested two-column card order. Schedule weekday headings align,
Fields labels and checkboxes use stable rows. At 390×844 all four primary screens
have scrollWidth equal to clientWidth (375 or 390 with scrollbar); Calendar also
fits 360×844. Photo confirmation/session recovery used a deterministic isolated
fixture; restore preview/cancel checked in-browser, replacement verified in tests.
Chrome app/Settings render with no captured console errors. Native PWA installation
and real OIDC/OCR/Stars remain unverified; do not label these as live-tested.

Safety: no live bot restart, bridge activation, legacy DB writes, production deploy,
paid requests or secret disclosure. Original bot.py author/link edits and untracked
welcome assets/outputs remain user-owned and excluded. Core changes are scoped.

Remaining limitations: natural-language photo follow-ups are not routed (explicit
one/all selections work); process-crashed reservations need audited operator recovery;
live cutover needs configured HTTPS/OIDC/bridge secrets and owner approval.
Next safe task: complete PWA install affordance and browser eligibility checks;
then review the documented cutover checklist without enabling production.
Rollback: keep bridge OFF to retain legacy runtime; preserve Core ledger and payment
outbox even during rollback. Restore user data only from explicit prior exports.

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
- Every lesson field is editable and persisted: weekday, subject, start/end time, location, room, teacher, lesson type, group, and notes.
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
commit: 7f5de90adcc17a32a2da694f2305be38b19575ec
branch: main
pushed: YES
purpose: complete schedule CRUD, reviewed import, responsive application navigation, and persistent settings
tests: 23 passed; Python compilation and JavaScript syntax checks passed
attack checks: validation bounds, overlap atomicity, malformed files, no-auto-save, Unicode, XSS rendering boundary, mobile containment
known limitations: see section above

## 2026-09-02 - Platonus import accuracy and UI regression cleanup

### Real PDF audit

- Inspected the complete six-page user-provided `Platonus.pdf` as extracted text and rendered A4 pages. The document is a tagged, unencrypted digital PDF with no embedded JavaScript or form fields.
- Confirmed that a weekday context can span page boundaries, a single time range can be split across physical lines, and the associated lesson text can continue across additional lines.
- Confirmed real empty slots, repeated consecutive slots, `Л`, `ЛЗ`, `СПЗ`, `СРСП`, academic titles, `Вакансия`, `МООК`, Kazakh/Russian names, campus rooms, and online rooms.
- The local parser found 23 actual slot-based lessons. Six are `СРСП`; the default preview therefore shows 17 and the explicit toggle shows all 23. No preview was confirmed during QA, so the user's schedule was not changed.

### Parser implementation

- Replaced the line-by-line digital PDF fallback with Platonus-aware grouping: detect weekday, detect a complete time range across line breaks, collect fragments until the next slot/day marker, then parse semantic fields.
- Empty slot groups are ignored. Consecutive lessons stay as independent rows; no speculative merging was added.
- Quoted lesson types are parsed generically rather than from a four-value allowlist, so unknown values such as `ПР-2` degrade safely.
- `subject`, `lesson_type`, `teacher`, `location`, and `room` are separated. Parenthesized academic titles, `Вакансия`, and `МООК` stay in `teacher`; campus/online location stays separate from the room.
- Added a bounded `location` field to the structured OpenAI contract, validated API model, SQLite schema, CRUD/import SQL, edit dialog, lesson display, and editable preview.
- Added a safe SQLite migration that gives existing lesson tables an empty `location` column without rewriting existing rows.
- Strengthened AI import instructions so image recognition follows the same semantic boundaries and continues treating document text as untrusted data.

### Preview and layout fixes

- Preserved the existing upload -> editable preview -> explicit confirm flow and its conflict/no-auto-save messaging.
- Preview keeps all recognized rows in memory, excludes exact normalized type `СРСП` by default, shows the excluded count, and restores those rows through `Импортировать СРСП`. Confirmation sends only the currently included rows.
- Rebuilt `Поля` rows as a fixed flex contract: equal width/height, label left, checkbox right. Desktop geometry was 180x36 for every row with aligned 17x17 controls.
- Fixed the mobile popover anchor after QA found that the desktop `right: 0` rule clipped labels off-screen. Mobile now anchors from the left and stays within the viewport.
- Rebuilt desktop Settings as two independent compact card columns, removing the grid-row whitespace between appearance and Student AI without adding placeholder settings. Mobile uses one ordered column.

### Tests and attack pass

- Added synthetic Platonus-format fixtures based on the real structure without copying the complete personal timetable into the repository.
- Regression coverage includes multiline grouping, subject/type/teacher separation, academic title, campus/room, online room, Unicode, `Вакансия`, `МООК`, unknown type, empty slots, consecutive slots, default СРСП exclusion contract, persistence, and old-database migration.
- Full suite: 29 passed. Python compilation and bundled Node.js syntax validation passed.
- Attack checks cover malformed/oversized files from the existing suite, 50,000-character PDF text bound, untrusted-document AI instructions, exact type filtering, empty/noise groups, footer removal, no speculative field guessing, atomic confirm, parameterized SQL, and DOM text/form rendering boundaries.
- Browser QA: real PDF preview 17 -> 23 through the toggle; desktop at 1440x1000; mobile at 390x844; zero console errors/warnings. Preview was closed without confirmation.

### Known limitations

- The parser targets the stable current Platonus exported-text grammar. A future radically different Platonus layout may need an additional parser variant.
- Scanned PDFs still require PNG/JPG conversion and an `OPENAI_API_KEY`; no local OCR dependency was added.
- Teacher strings preserve extracted academic titles as requested; typography inside initials/titles is normalized conservatively rather than guessed.

### Git checkpoint

Git checkpoint:
commit: b1153535e04cbc1dbfebe2a432478b47156170fc
branch: main
pushed: YES
purpose: accurate Platonus PDF grouping, default СРСП filtering, checkbox regression fix, and compact desktop Settings
tests: 29 passed; Python compilation and JavaScript syntax checks passed
attack checks: multiline/noise grouping, empty slots, unknown types, Unicode, file bounds, no-auto-save, atomic import, migration, desktop/mobile containment
known limitations: see section above

## 2026-09-02 - Deadline management and Settings card order

### Product changes

- Added one clear manual entry point, `+ Дедлайн`, to Today.
- Deadlines can now be created, opened from Today or Calendar, edited, deleted after explicit confirmation, and switched between active and completed in the same dialog.
- Manual and Student AI deadlines remain rows in the same owned `deadlines` table and use the same edit/delete flow. Saving immediately refreshes Today and Calendar.
- The focused model remains title, subject, date/time, description, completion status, and immutable origin. No recurring events, reminders, drag-and-drop, sync, authentication, or notifications were added.
- Desktop Settings columns now read `Внешний вид → Расписание` and `Student AI → Данные`; mobile remains `Внешний вид → Расписание → Student AI → Данные`.

### Tests and attack pass

- Full suite: 38 passed; only the existing Starlette/httpx deprecation warning remains.
- Covered past dates, existing date-only-to-midnight semantics, blank/oversized values, Unicode, duplicate submit idempotence, missing rows, foreign `user_id`, full CRUD, completion state, and Student AI deadlines edited through the common endpoint.
- Updates and deletes require both row id and `user_id`; SQL remains parameterized. Deadline text is rendered with `textContent`, not HTML injection.
- `git diff --check` passed. JavaScript syntax validation could not be rerun because Node.js was not on this shell's PATH; a fresh visual browser pass was intentionally not started after the explicit compute-limit instruction.

### Git checkpoint

Git checkpoint:
commit: 2441495
branch: main
pushed: YES
purpose: complete owned deadline CRUD, unified manual/AI editing, Today/Calendar interaction, and Settings card order
tests: 38 passed
attack checks: input bounds, date semantics, duplicate submit, missing/foreign rows, immutable origin, parameterized SQL, safe DOM rendering
known limitations: date-only API input uses midnight; visual browser QA was not rerun in this constrained checkpoint

## 2026-09-03 - Beta marathon factual audit and regression closure

Goal: verify the actual repository state and close the previous deadline checkpoint debts before auth work.

Starting HEAD: `ef7e5b9115b46360c53f6ffb6c7bde1f9fb92fc0` on `main`, identical locally, on `origin/main`, and on GitHub. The latest GitHub Actions run completed successfully.

Implementation:

- Corrected `README.md`: full deadline create/open/edit/delete/complete/reopen is now documented and no longer listed as missing.
- Located the bundled Node.js runtime and validated `static/app.js` syntax successfully.
- Ran desktop browser QA at 1440×1000 on a separate temporary SQLite database. Manual create, Today open, edit, complete, Calendar open, reopen, Unicode, and the delete-confirmation boundary worked. The temporary database was removed after QA.
- Verified desktop Settings geometry: Appearance and Schedule share the left column; Student AI and Data share the right column.
- Ran mobile QA at 390×844: one-column Settings order was correct, bottom navigation and menu were active, the page had no horizontal overflow, and the deadline dialog fit the viewport with vertical scrolling.

Security decisions:

- Browser QA used an isolated temporary database and did not touch the user's normal local data.
- Delete confirmation was opened but not accepted through browser automation; deletion behavior remains covered by the automated API/database tests.

Tests: 38 passed; Python compilation and JavaScript syntax validation passed.

Attack checks: duplicate submit, Unicode, past/date-only deadlines, missing and foreign rows remain covered; browser console showed no new application errors.

Changed files: `README.md`, `docs/DEVLOG.md`.

Git commit: `fb02b14` (`Correct deadline documentation`).

Pushed: YES, `main`.

CI: previous actual HEAD green; this documentation-only checkpoint will be verified after push.

Known limitations: authentication and production user isolation are still absent at this point in the marathon.

External blocker: none for the next internal-user/session foundation.

Next: replace `local-demo-user` with a verified server-side session identity and prove cross-user isolation.

## 2026-09-03 - Internal identity and server-side session foundation

Goal: remove production logic's dependency on `local-demo-user` and make every owned API operation derive identity from a verified server-side session.

Starting HEAD: `a283256cbe97e769a84c64d80046f0129d3d854d` on synchronized `main`.

Implementation:

- Added `users`, `sessions`, and `app_meta` tables. Student OS users have random stable UUIDs; Telegram will be an external identity, never the primary key.
- Added one-time legacy migration from `local-demo-user` rows to a stable internal development user, preserving lessons, deadlines, and preferences.
- Added cryptographically strong opaque session and CSRF tokens. Only SHA-256 session-token digests are stored server-side.
- Added session lookup, expiry, revocation, logout, and rotation on repeated development login. The browser receives an HttpOnly, SameSite=Lax cookie; production configuration adds `Secure`.
- Replaced every runtime `LOCAL_USER` use in bootstrap, Student AI, lesson CRUD/import, deadline CRUD, and preferences with the authenticated session's internal user id.
- Added CSRF validation to every state-changing authenticated endpoint. The frontend receives the CSRF value from its verified session and sends it as a header; it never supplies `user_id`.
- Local auto-login is available only when `DEV_LOGIN_ENABLED=true` and is always disabled in `APP_ENV=production`. The default loaded configuration is fail-closed until the developer explicitly enables it.

Security decisions:

- Sessions are server-side and revocable; modifying the cookie produces no valid identity.
- Login rotates away from any browser-provided cookie to prevent session fixation.
- Missing, invalid, expired, and logged-out sessions receive 401. Missing or modified CSRF headers receive 403.
- Every owned query continues to bind `user_id` in SQL. Cross-user reads return only the current user's bootstrap data; cross-user mutations return not-found.
- The old literal `local-demo-user` remains only inside the bounded migration path, not request handling.

Tests: 44 passed; Python compilation and bundled Node.js syntax validation passed.

Attack checks:

- Missing cookie, arbitrary cookie, expired session, logout reuse, fixation input, absent/modified CSRF, browser-supplied `user_id`, user A reading user B data, direct foreign lesson update, foreign deadline delete, and legacy migration idempotence.
- Existing malformed input, duplicate submit, Unicode, schedule conflict, import atomicity, and deadline ownership regressions remain green.

Changed files: `.env.example`, `README.md`, `app/auth.py`, `app/config.py`, `app/database.py`, `app/main.py`, `static/app.js`, auth and existing endpoint tests.

Git commit: `0662405` (`Build secure user session foundation`).

Pushed: YES, `main`.

CI: push triggered; local suite green. Remote result will be rechecked at the next checkpoint.

Known limitations: there is not yet a production login method, account recovery flow, session management UI, or Telegram identity table. A public deployment would therefore reject all application API access rather than silently enabling development login.

External blocker: none for Telegram verification code and fixtures. Live Telegram use later requires bot credentials and a configured domain.

Next: implement Telegram signature/freshness verification and external account-link mapping without touching the live bot database.

## 2026-09-03 - Telegram identity and Student AI entitlement boundaries

Goal: implement the maximum safe Telegram/account-link and credit foundation that does not require credentials, a domain, or writes to the live bot ledger.

Starting HEAD: `ab6dac1` on synchronized `main`.

Implementation:

- Added server-side Telegram Login Widget HMAC-SHA-256 verification, bounded fields, constant-time hash comparison, `auth_date` freshness with future-skew bound, and single-use replay keys.
- Added `external_identities`: Telegram IDs map uniquely to internal Student OS users and never become primary keys. Verified login finds the same user or atomically creates a new one.
- Added authenticated account-link endpoint with same-user idempotence and explicit conflicts for one Telegram identity across users or a second Telegram identity on one user.
- Kept unlink fail-closed while Telegram would be the only production recovery/login method; the active session cannot silently make its account unrecoverable.
- Added honest Settings state for configured/unconfigured/linked Telegram and connected/unconnected credits.
- Added `StudentAIEntitlementService` protocol and a local unconnected implementation with balance, unlimited, reserve, commit, and release operations.
- Credit reservations are bound to internal user + request ID, atomic under `BEGIN IMMEDIATE`, idempotent on retry, non-negative, concurrency-safe, and refund exactly once before commit.
- The entitlement source reports `local-unconnected` and is not used to block Student AI until a reviewed live source is connected. Core organizational features never depend on credits.

Security decisions:

- Bot token stays in environment and never enters frontend state or responses.
- Missing Telegram configuration returns 503; forged/stale/future/replayed payloads fail without creating a user/session/link.
- Exact replay prevention is stronger than the legacy widget's bare freshness check. The recommended live UI upgrade is Telegram's current OIDC Authorization Code + PKCE flow after registering a domain/redirect URL.
- No direct shared-SQLite writer was added against `student-ai-bot`; concurrent processes writing its live ledger would be unsafe.

Tests: 51 passed; Python compilation, JavaScript syntax, and diff checks passed.

Attack checks: forged hash, post-signature field tampering, stale/future auth date, replay, duplicate linking, cross-user identity conflict, unconfigured token, duplicate credit request, request ID stolen by another user, insufficient balance, concurrent double-spend, repeat commit/release, and release after commit.

Changed files: config/env, database schema, Telegram verifier, entitlement service, auth endpoints/bootstrap, Settings status, Telegram/bridge docs, and focused tests.

Git commit: `6d86955` (`Add Telegram identity and credit bridge boundaries`).

Pushed: YES, `main`.

CI: push triggered; remote result will be rechecked at the next checkpoint.

Known limitations: no live OIDC/widget UI, account recovery, bot-ledger adapter, migrated balance, payment handling, or production enforcement. Current Student AI behavior is deliberately preserved while the credit source is unconnected.

External blocker: Telegram Client ID/Secret or bot token, BotFather allowed domain/redirect configuration, approved production domain, and a staging copy/reviewed adapter for the bot ledger.

Next: build the deny-by-default web admin shell, role policy, privacy-minimal overview/users, safe credit controls, feedback, and admin audit log.

## 2026-09-03 - Secure admin control center and low-contact feedback

Goal: give the product owner a compact operational web panel while denying ordinary users and avoiding surveillance-oriented access to private student content.

Starting HEAD: `39cb57e` on synchronized `main`; Telegram/credits feature CI was green.

Implementation:

- Added server-enforced `admin` role policy to `/admin` and every `/api/admin/*` endpoint. Client-side visibility is convenience only and never authorizes access.
- `ADMIN_TELEGRAM_ID` promotes a user only after a correctly signed, fresh, single-use Telegram login payload matches the configured external identity.
- Added overview counts for users/recent users, Student AI usage, schedule imports, deadlines, and feedback polarity.
- Added bounded search/pagination by internal ID, display name, and minimal Telegram link metadata. User detail exposes identity/link, entitlement summary, high-level usage, and relevant admin action history—not schedules, deadline text, notes, or assignment content.
- Added credit and unlimited mutations with bounds, required reason, CSRF, request-id idempotence, negative-balance prevention, and atomic audit rows. Reusing a request ID for a changed actor/target/action/value/reason is rejected.
- Mutations remain disabled and return 409 while `ENTITLEMENT_SOURCE=unconnected`; explicit `local` mode is available for staging/local source-of-truth tests only.
- Added product feedback form and Student AI 👍/👎 action. Feedback is user-owned, size-bounded, idempotent per request ID, and rendered with `textContent`.
- Added minimal server-side events for completed Student AI analysis, confirmed schedule import, unique deadline creation, and feedback submission. No assignment, answer, schedule, note, or deadline body is stored in events.

Security decisions:

- An ordinary authenticated user receives 403 from both the admin page and direct admin API calls.
- Admin mutations require both admin role and the session's CSRF token. Role is never accepted from request payloads.
- Every meaningful entitlement mutation logs actor, timestamp, action, target, delta/state, reason, result, and idempotency key; secrets are never logged.
- Admin UI intentionally omits private content and uses safe DOM text nodes for untrusted feedback/user fields.

Tests: 57 passed; Python compilation, both JavaScript syntax checks, and diff checks passed.

Attack checks: manual admin URL by normal user, direct normal-user credit request, missing admin CSRF, missing target, zero/oversized/negative adjustment, missing reason, request-id replay with changed input, unconnected source mutation, XSS-shaped feedback, duplicate feedback, and no-private-content response contract.

Changed files: env/config, database/admin/feedback/event schema, main API, entitlement source mode, Student OS Settings/feedback UI, standalone admin HTML/CSS/JS, README, and security tests.

Git commit: `e1940b2` (`Build secure admin and feedback foundation`).

Pushed: YES, `main`.

CI: push triggered; local suite green, remote result will be rechecked next.

Known limitations: no live payment/ledger connection, production OIDC UI, richer retention policy, or separate support workflow. Recent user activity is based on authenticated API access, not invasive tracking.

External blocker: live admin credit control remains intentionally disabled until an authoritative ledger adapter and migration are approved.

Next: versioned owned-data export, installable PWA shell without authenticated API caching, production/deployment contract, then a consolidated security attack pass.

## 2026-09-03 - Owned-data export, safe PWA, and deployment foundation

Goal: complete the beta-foundation marathon with a useful user-owned backup boundary, installable mobile shell, deployment contract, and a consolidated attack pass without starting production deployment.

Starting HEAD: `772d1f5` on synchronized `main`; admin/feedback feature CI was green.

Implementation:

- Added `OwnedDataExportService` and authenticated `GET /api/export`. The UTF-8 JSON contract is versioned and contains only preferences, lessons, and deadlines owned by the verified session user.
- Removed `user_id` from every exported object. Sessions, CSRF, Telegram identity, credentials, feedback, analytics, entitlements, and admin/audit records are outside the format by design.
- Bounded a single export to 10,000 lesson/deadline records and 5 MiB serialized output; overflow fails with 413 instead of streaming an unbounded response.
- Added a real Settings download action. Restore/replace remains an honest future feature with a documented preview, validation, explicit confirmation, and atomic transaction contract.
- Added a Russian PWA manifest, standalone metadata, vector maskable icon, and service worker. It precaches only the public HTML/CSS/JS/manifest/icon shell and explicitly bypasses `/api/*`, `/admin*`, cross-origin, and non-GET requests.
- Added a Procfile-compatible ASGI start command, `BETA_FOUNDATION` health stage, and `docs/DEPLOYMENT.md` covering persistent SQLite storage, HTTPS, secrets, fail-closed login, and staging checks.

Security and privacy decisions:

- Export identity comes only from the server-side session; there is no request `user_id` or foreign-record selector.
- Keeping stable lesson/deadline record IDs supports a future restore preview, while the absence of owner IDs prevents importing another account identity.
- The service worker deliberately provides no offline authenticated data or background sync. A shell can open offline, but schedules/deadlines must be loaded from the authenticated API online.
- Production remains fail-closed without Telegram login configuration. No provider, paid resource, database, domain, or deployment was created.

Tests: 60 passed; Python compilation, application/admin/service-worker JavaScript syntax, and diff checks passed. Feature CI for `de7e643` completed successfully.

Attack checks:

- Missing session export, cross-user deadline isolation, sequential foreign record exclusion, Unicode round-trip, and absence of internal user IDs/API keys/session/CSRF/Telegram/private foreign text.
- Artificial record-count and serialized-byte overflow both return 413.
- PWA contract tests assert install metadata and explicit `/api` plus `/admin` cache bypass.
- Existing auth fixation/logout/expiry, CSRF, Telegram signature/freshness/replay, ownership, admin denial/tampering, credit concurrency/idempotence, XSS-shaped feedback, malformed input, duplicate submit, and Unicode regressions remain green in the full suite.

Browser QA:

- Desktop Settings exposes the export in the existing Data card; clicking it completed a real authenticated download and showed `Экспорт готов`.
- Mobile 390×844 preserved the one-column card order, fixed checkbox alignment, and had no horizontal overflow (`scrollWidth` 375 at a 390 px viewport).

Changed files: export service/API/tests, Settings download UI, manifest/icon/service worker, README, Procfile, and deployment documentation.

Git commit: `de7e643` (`Add owned export and safe PWA foundation`).

Pushed: YES, `main`.

CI: GREEN for `de7e643`.

Known limitations: JSON restore is not implemented; the SVG manifest icon should receive PNG fallbacks before broad device-matrix release; PWA has no offline user data; SQLite needs one persistent-volume web instance until a reviewed multi-instance database migration exists.

External blockers/manual steps: configure Telegram production credentials/domain or OIDC redirect, set `ADMIN_TELEGRAM_ID`, select and mount persistent storage, connect a reviewed authoritative Student AI ledger adapter, and perform staging device QA before sharing a public link.

Deliberately omitted: production deploy, paid resources, live bot database writes, cloud sync/restore, payments, offline sync, Contacts, Knowledge Base, OCR, native apps, recurring calendar, and redesign.

Next: stop at this stable foundation. The next scope should start from production Telegram UI/account recovery plus a reviewed entitlement adapter and staging deployment, not from additional unrelated features.

## 2026-09-03 - Product polish and Student AI integration preparation

Goal: fix local admin access, make the Student AI account/credit boundary honest, improve mobile Calendar and product identity, then begin a safe shared-engine integration without touching the live Telegram bot or ledger.

Starting HEAD: `fcf9d0b8b6b473c4781cc27dc8734dbe0a94a8c6` on clean synchronized `main`; GitHub Actions was green.

Audit:

- Confirmed `/admin` correctly denied the ordinary development user but had no explicit local owner path.
- Confirmed the Student AI form called the engine without checking Telegram identity or entitlement state.
- Confirmed the smallest mobile breakpoint reduced deadlines to 7 px dots and had no multiple-event overflow policy.
- Confirmed the green E-shaped favicon was unrelated to the black/purple Student OS UI.
- Re-audited `C:\student-ai-bot` read-only at `5a9ce776a6e60a3879f51263443d9c89c115f7c1`: bounded Responses continuation, text/photo flows, 24-hour recognized-photo context, token/cost accounting, trial/paid/unlimited access, explicit restore on failure, defense follow-up, and relevant tests. Its pre-existing dirty files remained untouched.

P0 - local admin access:

- Added `DEV_ADMIN_ENABLED`, default false. It promotes only the stable server-selected development user and only when `APP_ENV=development` plus `DEV_LOGIN_ENABLED=true` are also active.
- Development login resets the local user's role to ordinary user when the flag is off, preventing a previous local admin session from silently preserving access.
- Production ignores dev-admin configuration and additionally requires an admin-role session to have a verified Telegram identity equal to `ADMIN_TELEGRAM_ID`.
- Regression tests prove an erroneously enabled development login/admin pair cannot open the page or API in production, even with a manually created admin-role user lacking the verified owner identity.

P1/P2 - Student AI gate and web preparation:

- Student AI stays visible to every authenticated Student OS user. Its left pane now shows account/entitlement status and an honest disabled future photo/file boundary; the structured right pane retains understanding, solution, approach, checks, `Как защитить`, teacher questions, pitfalls, feedback, and deadline confirmation.
- Without a Telegram identity, both browser and backend stop before entitlement lookup, reservation, or engine execution. The modal explains that Telegram is required only for Student AI and links to account Settings.
- A linked identity proceeds to entitlement validation. `local-unconnected` returns an honest beta state without a fake balance or engine call.
- A connected source performs reserve → engine → token-accounted commit. Failure releases the reservation; reusing a request ID is rejected before a second engine invocation.
- Bootstrap no longer creates entitlement rows for unlinked users. Schedule, Today, Calendar, Deadlines, Settings, and export remain independent of Telegram and credits.

P3/P4 - Calendar and icon polish:

- Mobile Calendar now stacks up to two full-width subject/title pills per day and displays `+N` for additional deadlines. Text truncates inside the grid; the entire pill opens the existing deadline dialog.
- Desktop Calendar styling and interaction remain unchanged.
- Replaced the unrelated green letter with a neutral black/purple abstract Student OS panel mark aligned to the existing UI system.
- Added SVG favicon, maskable PNG fallbacks at 192×192 and 512×512, Apple touch metadata, updated manifest colors, and service-worker cache version/assets.

P5 - shared Student AI engine preparation:

- Ported the old bot's bounded continuation principle into the structured web engine: only `max_output_tokens` truncation continues, at most four Responses calls, with every call retaining `store=False` and strict JSON Schema.
- Because web output is one structured object, a continuation regenerates one complete valid JSON object from accumulated response context instead of concatenating Telegram-style Markdown fragments.
- Subject/title are now explicit engine context rather than fallback-only UI fields. Input/output token totals across continuations are persisted on the committed reservation and bounded before storage.
- Analytics writes became best-effort so an optional event failure cannot turn an already committed successful answer into a user-visible AI failure.
- Added `docs/STUDENT_AI_ARCHITECTURE.md`: exact old bot → reusable domain → Telegram/web mapping, photo compatibility fixtures, single-writer ledger migration, staged rollout, rollback, and manual prerequisites.

Tests: 69 passed; Python compilation, application/admin/service-worker JavaScript syntax, and diff checks passed. CI is green for P0-P4 commit `45c5acb` and P5 commit `cb49ecc`.

Attack checks:

- Local admin flag absent/off, ordinary-user admin denial, production dev-admin misconfiguration, role-only production escalation, missing admin CSRF, and verified Telegram owner path.
- Unlinked Student AI request creates no entitlement/reservation and makes zero engine calls; linked-unconnected makes zero engine calls; connected request commits once; duplicate request does not rerun; failure refunds.
- Legacy reservation schema migration, token aggregation across continuation, hard four-call limit, strict structured output, `store=False`, malformed/oversized input, Unicode, and existing auth/Telegram/ownership/credit concurrency suites.
- PWA never caches API/admin responses; SVG/PNG signatures and manifest sizes are checked.

Browser QA:

- Desktop 1440×1000: development admin opened the real control center and loaded overview/users/feedback/audit APIs.
- Student AI without Telegram displayed the gate while leaving form and organizational navigation available.
- Mobile 390×844: three deadlines on one date rendered two truncated horizontal pills plus `+1`, pill tap opened edit dialog, and document width stayed below viewport width.
- Browser loaded the new favicon, manifest, Apple touch icon, and both PNG manifest icons.

Git checkpoints:

- `45c5acb` - `Polish beta access and Student AI gate` - pushed, CI green.
- `cb49ecc` - `Prepare shared Student AI engine integration` - pushed, CI green.

Known limitations/blockers:

- The Telegram connection CTA currently leads to the honest account Settings state; live OIDC/widget UI still requires production client/bot credentials and allowed domain/redirect setup.
- `ENTITLEMENT_SOURCE=local` remains staging-only. A staging ledger copy, authenticated single-writer adapter, reconciliation, and migration approval are required before live balances can be enforced.
- Photo upload remains disabled until MIME/signature/dimension limits, explicit quoted credit cost, 24-hour recognized-text storage, repeat-confirmation safety, and device QA are implemented.
- Completed request replay currently returns conflict instead of a cached answer. A shared service may add encrypted/retention-bounded response replay later.

Deliberately omitted: live bot or database changes, Telegram handler imports, production deployment, Contacts, Knowledge Base, OCR, cloud sync, offline user data, payments, recurring calendar, and redesign.

Next: implement the production Telegram connection UI and a staging-only authoritative entitlement adapter, then exercise the sanitized text/photo compatibility fixtures before any live migration.

## 2026-09-03 - Pre-integration regression checkpoint

Goal: close the two release-blocking regressions before starting the unified-core work.

Implementation:

- Direct navigation to `/admin` now bootstraps and rotates a server-side session for the stable local development user when `APP_ENV=development`, `DEV_LOGIN_ENABLED=true`, and `DEV_ADMIN_ENABLED=true` are all explicit.
- Development bootstrap remains disabled by default. Production still requires an admin-role session backed by a cryptographically verified Telegram identity equal to `OWNER_TELEGRAM_ID=8247777174`; a role-only session and any other verified Telegram account are denied.
- Renamed the active owner setting from `ADMIN_TELEGRAM_ID` to `OWNER_TELEGRAM_ID` in code and current setup/deployment documentation.
- Moved the schedule's `Сегодня` marker outside normal desktop heading flow. A fixed heading row now keeps weekday labels and first lesson cards aligned; mobile retains a natural two-line current-day heading.

Tests and attack checks:

- 71 pytest tests passed, including new direct-bootstrap, stale-session rotation, production owner/non-owner, and schedule-header contract regressions.
- Python compilation, JavaScript syntax, and `git diff --check` passed.
- Attack cases covered: missing/off development flags, development flags set in production, forged role-only production admin, verified non-owner Telegram account, stale ordinary local session, and duplicate cookie/session rotation behavior.

Browser QA:

- Direct local `/admin` opened the real control center without a manual login or DevTools preparation under the explicit development flags.
- Desktop 1440×1000: Monday-Friday weekday headings shared the same Y coordinate, and every first lesson/empty card shared the same Y coordinate; `Сегодня` rendered above Thursday without shifting that column.
- Mobile 390×844: the marker stacked above the weekday, all schedule rows remained usable, and the document did not overflow horizontally (`scrollWidth` 375 at a 390 px viewport).

Known limitation: another inaccessible stale local process occupied `127.0.0.1:8000` during QA, so the current checkout was exercised on isolated local port 8001. The application route and configuration path are identical; no deployment or live configuration was changed.

Next: commit and push this regression-only checkpoint. Begin the unified ledger/bridge work only from that green state.

## 2026-09-03 - Unified ledger and signed Core bridge

Goal: make Student OS Core the forward-looking source of truth before changing the Telegram bot.

Starting HEAD: `49c089573188da0f78e06b7220d70082fb462e19` on clean synchronized `main`; CI was green.

Implementation:

- Expanded one transactional entitlement boundary to own the shared free trial, paid credits, unlimited state, amount-aware reservations, access source, token totals, and commit/release timestamps.
- Added the authoritative Telegram Stars catalog matching the audited bot source: `task_help_1_v1` = 25 Stars / 1 credit and `task_help_5_v1` = 100 Stars / 5 credits.
- Added idempotent payment accounting keyed by Telegram payment charge ID. Product, expected Stars, and granted credits are resolved only in Core.
- Added narrow signed Core operations for products, Telegram identity resolution, entitlement lookup, canonical text analysis, and successful Stars delivery. Telegram requests never select an internal UUID.
- Added a Web purchase handoff to Telegram `/start buy`, explicit balance refresh, focus/visibility refresh without polling, and honest trial/balance/unlimited state.
- Connected admin overview/user detail to reservations, success/release counts, Stars totals, outstanding credits, unlimited users, token totals and payments; added audited trial restoration.
- Changed the service worker shell strategy to network-first with offline cache fallback and versioned critical assets, preventing stale admin/application JavaScript after an update.

Security:

- Bridge authentication uses HMAC-SHA-256 over timestamp, nonce and exact body, constant-time comparison, bounded freshness/body size, durable replay rejection, and a per-process rate ceiling.
- Missing bridge secret fails closed with 503. Browser session/CSRF credentials are not bridge credentials.
- Balance cannot become negative; duplicate request, duplicate payment and all admin mutations are transactional and idempotent at their respective keys.
- No production secrets or legacy bot data were copied. The live bot and its database were not changed in this phase.

Tests: 79 Student OS tests passed; Python compilation, application/admin JavaScript syntax and diff checks passed. New tests cover shared-trial release/race behavior, unlimited non-decrement, identity stability, exact products, duplicate/wrong/unknown payments, canonical semantic result, token commit, bad HMAC, stale timestamp, replay, tampering, and unconfigured bridge.

Attack checks: verified duplicate charge cannot double-credit; a reused charge ID cannot be rebound; a duplicate AI request does not rerun the engine; failed AI restores the trial; arbitrary product/amount/internal user fields are rejected; bad/stale/replayed/tampered signatures fail.

Browser QA: on isolated local port 8001, development owner opened the updated admin, loaded overview/users/feedback/audit, and opened unified user detail with trial/usage/payment controls. The connected Web fixture showed one free attempt, the Telegram deep link, manual refresh, and focus refresh; a real demo analysis consumed the shared trial and rendered checks plus `Как защитить`. Desktop width remained contained.

Changed files: configuration, database schema/migrations, unified entitlement service, HMAC bridge authentication, Core routes/models, Web Student AI purchase/refresh UI, admin UI, service worker, tests, README and architecture/deployment/Telegram documents.

Commit: `6225ab181564066747e8512265e7129a87fd6c3f` (`Build unified Student AI core ledger`).

Push: YES, `main`.

CI: GREEN, GitHub Actions run `33744359026`.

Limitations: bot adapter/outbox is not yet changed; bridge remains unused by the live bot. Photo UI remains disabled. The existing inaccessible process still owns localhost port 8000, so this checkout's browser QA uses port 8001.

Blockers: live cutover still needs a production Core URL plus a shared secret installed in both services; this does not block implementation/testing.

Low-usage stop: the default-off bot adapter/outbox was briefly scaffolded but could not be completed safely within the remaining usage. Those incomplete bot edits were removed; the bot worktree was restored exactly to its pre-existing state (`app/bot.py` owner/GitHub rename plus untracked welcome assets/outputs only).

Next: from Student OS `6225ab1` and bot `5a9ce77`, implement the bot adapter as one bounded unit: add default-off config + signed client + durable payment outbox, route bridge-mode balance/products/text/payment delivery while preserving legacy mode, add outage/idempotency tests, then commit only intentional bot files without staging the pre-existing assets/outputs.

## 2026-09-03 — Resumed bot integration checkpoint

Goal: finish the paused bridge unit before proceeding with the beta-readiness brief.
Starting HEAD: Student OS `2e6eff5`; bot `5a9ce77`. Local/origin matched. Core CI green;
bot initially had no CI. Pre-existing bot owner/GitHub rename and welcome assets/outputs
were preserved, excluded from both commits, and remain the only dirty bot files.

Architecture: Core remains the only forward ledger/engine. Bot uses a signed transport
and separate durable delivery journal; legacy DB/schema are unchanged. Default flag OFF.

Implementation: HTTPS-origin client (loopback HTTP for tests), no redirects, bounded
request/response, timeouts, safe errors; idempotent outbox with receipt matching and
concurrent-failure protection; first-priority bridge dispatcher; Core balance/catalog;
five-second pre-checkout fail-closed; stable Telegram message request IDs; plain-text
bounded answer formatting; cached one-hour defense without duplicated AI generation;
startup/60-second retry worker replacing legacy reactivation in bridge mode.
Old photo/defense/admin/referral mutation paths are blocked in bridge mode, not deleted.

Security/attack: exact Unicode signing, HTTPS policy, malformed/oversized responses,
no raw transport exception logging, durable outage/reopen, duplicate/conflicting charge,
invalid receipt, late failed retry, checkout outage, default-OFF no-op, bounded formatting.
Staged diffs checked for credentials; no tokens, cookies, DBs or private records committed.

Tests: baseline Core 79, bot 60. Final bot 70; Core 82 including three cross-project
scenarios. Python compile and diff checks pass. Initial bot sandbox temp-directory ACL
failure resolved by running isolated tests with approved filesystem access; an outbox
connection-close defect found by Windows tests was fixed before commit.

Integration: real bot client/outbox against Core ASGI with a deterministic engine fixture;
both directions of shared trial, stable identity, admin credit visibility, unlimited,
engine contract, failed request refund, duplicate request, 25/100 Stars, wrong amount,
unknown product and outage retry. No paid AI/Stars call. CI pins tested bot checkout.

Browser QA: not repeated for this backend/Telegram-only change; no Web assets changed.
Changed files: bot client/outbox/config/dispatcher/runtime hookup/tests/CI/docs/env example;
Core cross-project tests, CI and bridge/DEVLOG documentation.

Commits: bot `6543f7d` client/outbox; `d0e048b` adapter. Both pushed to main.
CI: both GREEN (`33792108669`, `33792842618`). Core integration checkpoint pending commit.

Known limitations: photo not yet shared; feedback/legacy controls blocked in bridge mode;
defense expires on process restart; AI duplicate returns conflict, not cached response;
process-crashed reservations still need recovery policy. Outbox errors remain pending
for operator review/retry, with no automatic deletion. Live setup not exercised.

External blockers: live HTTPS Core, credentials and manual cutover; none block offline work.
Rollback: flag OFF plus explicitly authorized restart restores legacy behavior; retain
pending outbox and reconcile paid records before retiring Core. No live restart, bridge
enablement, legacy DB modification or production deployment was performed.
Next: harden bridge security/operational edge cases, then continue the prioritized brief.

### Bridge security follow-up

Core integration checkpoint `c3a0092` was pushed. Attack review found that the original
signature did not bind the endpoint and body size was checked after JSON ingestion.
Protocol v2 now signs method/path + timestamp/nonce/body; old signatures fail closed.
An ASGI boundary caps bridge bodies before FastAPI parsing. Header syntax/length is
validated before integer conversion/constant-time compare, avoiding malformed-header 500s.
No live client uses this protocol yet; both repositories must be deployed together.

Tests: 11 focused bridge/integration tests passed; bot 70 passed. Added endpoint-swap,
oversized invalid JSON, oversized timestamp, non-ASCII headers and rate-limit tests.
Bot commit `2fbcc37` pushed; Core CI pins that compatible transport revision.
No Web UI change; browser QA not applicable. Secrets scan and diff checks pass.
Rollback is still flag OFF; no production runtime or database was touched.
Next: operational account/admin review and production Telegram UI foundation.

## 2026-09-04 — Telegram account/login foundation

Goal: finish an actual production login UI boundary without using live credentials.
Starting HEAD: Core `78e154a`, bot `2fbcc37`; both CI GREEN.
Architecture: Telegram documented OIDC Authorization Code + PKCE, RS256-only JWT
verification via PyJWT/cryptography. Existing internal UUID/session/link policy retained.

Implementation: five-minute single-use browser-bound state, PKCE verifier, bounded
pending attempts and token response; fixed Telegram token/JWKS endpoints; HTTPS registered
callback configuration; constant-time session/browser binding; token issuer/audience/
expiry/issued-at/Telegram-id validation. Login rotates session; authenticated linking
requires CSRF and rejects existing-account conflicts without implicit merge or data loss.
Logout confirmation, honest missing-configuration state, Settings balance/purchase/refresh,
production login screen and safe callback notices. No phone or bot-write scope requested.
Raw tokens not stored; callback no-store/no-referrer; Uvicorn access logs disabled to avoid
authorization-code logging. Reverse proxy redaction remains an operator requirement.

Tests: eight focused OIDC/legacy auth tests passed, including real generated RSA signature,
forgery, wrong issuer/audience, stale/expired, invalid id, state-cookie mismatch, replay,
CSRF, account conflict, owner promotion and logout. No live Telegram/paid calls.
Browser: actual local port 8001, isolated `data/account-qa.db`; desktop 1440×1000 Settings
retains appearance/schedule left and AI/data right. Mobile 390×844 width stayed 375;
logout confirmation and disabled login screen verified; 360px login screenshot contained.
No real login/domain verification claimed. JS syntax/diff checks pass.

Changed files: OIDC module/config/routes/tests/dependency, account JS/HTML/CSS/SW, env
example, run commands and docs. Known limitations: RS256 only, no automated account
merge; real BotFather domain/credentials and staging login required. Existing photo/restore
backlog remains. Rollback: remove OIDC env; legacy HMAC boundary remains; no DB deletion.
Next: shared photo domain after this tested checkpoint, then restore and final QA.

## 2026-09-04 — Shared photo domain and adapters

Goal: preserve old photo setup semantics while using one Core ledger/engine.
Starting HEAD: Core `a5a3818`, bot `2fbcc37`. OIDC checkpoint pushed; live credentials unused.
Architecture: adapter-independent PhotoService with expiring quotes/session/request tables;
Core owns recognition, task selection, setup charge and token accounting. Both adapters
call it. Legacy bot path remains unchanged with bridge OFF.

Implementation: PNG/JPEG MIME/signature/decoder checks, 6 MiB and 16M-pixel bounds,
animation/corruption rejection; no filenames used as paths. Five-minute quote binds user,
image digest and entitlement source. Explicit confirm atomically claims quote, reserves
one shared trial or five credits, recognizes tasks, then commits session + usage in one
transaction; failure releases reservation. A changed source never silently becomes paid.
Maximum 30 recognized tasks/24K characters; no raw photo persistence. Tasks logically
expire at 24h and are purged on access/startup and by a 60-second cleanup worker.
Free follow-ups have stable request IDs, duplicate rejection and 20/hour ceiling.
Photo request/token counts feed existing admin totals without revealing task content.

Web: upload → quote → confirm → selectable task list → canonical result/defense.
Latest session restores after reload. Telegram: same quote/confirm flow, one/all selection
buttons, shared defense, five-minute in-memory raw-photo expiration; session recovery after
restart; stale buttons cannot target a newer photo. Regular text and legacy mode preserved.
Bridge body limit is 9 MiB only for the two base64-photo operations; all other endpoints
retain 64 KiB and path-bound HMAC. No raw image/auth payload is logged.

Tests: focused domain cases cover validation-before-AI, trial, paid refund, changed quote,
concurrent/double confirm, Unicode/unreadable tasks, selection, IDOR, expiry and purge.
Cross-project test proves Telegram setup followed by Web and Telegram selections without
extra debit. Bot suite 71 passed. Python/JS syntax and diff checks pass; full Core result
recorded at the checkpoint. Browser uses explicit `tests/qa_photo_app.py` fixture only.

Browser QA: 1440 desktop quote/confirmation/list/result/defense; 390×844 task checkboxes
and actions fit with scrollWidth 375; reload recovers the same three-task session. Synthetic
white PNG/deterministic engine, not a live OCR quality test or paid request. QA DB isolated.

Known limitations: free follow-up failure does not refund a successfully completed recognition
setup; UI quotes explain that setup buys the recognized-photo session. Process-crashed
reservations still require operator recovery policy. Selection is one/all in Telegram and
arbitrary checkboxes in Web; natural-language photo follow-ups are not auto-routed yet.
Raw upload is request-scoped/spooled temporarily by the framework; no application file store.
Rollback: bridge OFF for bot; unset AI key disables Web photo; retain Core ledger/outbox.
No live bot restart, real payment, legacy DB write or production deploy occurred.
Next: safe JSON restore, final security/browser/deployment readiness pass.

Photo checkpoint verification: full Core suite **92 passed**, bot **71 passed**.
Bot `cb83d2d` pushed; Core CI pins this exact compatible revision. Both runtime feature
flags remain unchanged. Temporary synthetic PNG removed after browser QA; isolated
ignored QA database retained only for reproducibility. No user-provided asset removed.

## 2026-09-04 — Safe restore and ingress/cache hardening

Goal: owned-data restore without identity/ledger changes or partial persistence.
Starting HEAD: Core `17a4d0b`, bot `cb83d2d`; both CI GREEN.
Architecture: existing domain validators; five-minute preview hashes bound to user/file/
current snapshot. Confirm revalidates and replaces lessons/deadlines/preferences in one
BEGIN IMMEDIATE transaction. Changed file/data, expired/replayed/foreign preview fail closed.
New IDs; private/unknown fields, duplicate JSON keys/deadlines, overlaps and bad values rejected.
Limits: 5 MiB/10K records. No account/credits/payment mutation.

UI: upload, before/after counts, replacement checkbox, disabled confirm until consent,
current-export warning and cancellation. Browser: 390×844 preview/disabled confirm/cancel
on isolated QA DB. Actual replacement and database-error rollback verified by automated
tests, not claimed as browser-confirmed.
Security: upload caps before multipart parsing; API/admin no-store; no-referrer/nosniff;
SW caches explicit public shell only. Signed health exposes mode/readiness/pending count.
Tests: **97 Core tests passed**, including roundtrip, rollback, IDOR, CSRF, snapshot conflict,
duplicate confirmation, malformed/private-field archives. Python/JS syntax/diff checks pass.
No production credentials or actions. Changed files: restore service/routes/UI/tests,
ingress, headers, SW, deployment and DEVLOG. Rollback: disable restore UI/routes; actual
data rollback requires an explicit prior export, never silent DB-file replacement.
Next: remaining small operational/documentation gaps and synchronized final checkpoint.

## 2026-09-04 — Heroku PostgreSQL foundation, no live cutover

Scope: one authorized Essential-0 and the Core PostgreSQL storage boundary only.
Starting Core HEAD d92b671; bot f6e4552 remains unchanged by this checkpoint.
After explicit owner approval of add-on terms/MSA, provisioned exactly one database:
postgresql-animate-45477, Essential-0 ($5/month), Core DATABASE attachment, created.
Shared Eco subscription + this database target $10/month; Student credits cover up
to $13/month while eligible, not an unrestricted $312 wallet. No additional paid
resources. Both cloud apps still have no deployed code/dynos; local bot not restarted.

Implementation: PostgreSQL repository adapter preserves existing canonical users,
sessions, owned data, ledger, payments, replay guards, admin audit, OIDC, photo and
restore services. SQLite remains local/test storage. Environment-loaded staging/
production requires DATABASE_URL; DYNO defaults to production; staging also disables
development login/admin bootstrap. Heroku-managed URL is never stored in Doppler/Git.
Versioned SQL migrations have transactional application, checksums and advisory lock.
Connections are bounded to four per process and close after each unit of work; remote
TLS required. Short repository transactions are serialized for beta correctness.
AI calls run outside these transactions. This is not a high-throughput design.

ATTACK: initial real-Heroku run found SUM(boolean) incompatibility and SQLite rowid
in restore snapshots (3 failures, 17 passes). Replaced both with portable SQL and
explicit aggregate aliases. Added real PostgreSQL domain regressions for concurrent
trial/credit use, refunds/idempotency, user isolation, sessions/CSRF/admin policy,
Stars validation/replay, OIDC, export/restore, photo and transactional migration failure.
Tests create disposable test_* schemas only, never modify public tables. The managed
database URL passes directly in memory to the test subprocess; no values are printed.

Verification: full SQLite/cross-project suite 102 passed, 24 PostgreSQL cases skipped
without the test URL; Python compile, PWA runtime and diff checks passed. Final real
Heroku PostgreSQL rerun: **27 passed** in 737 seconds, including all initial failures.
Known warning: Starlette TestClient/httpx deprecation, no runtime failure. Staged
credential-pattern check passed with only the disposable localhost CI URL allowlisted.
Heroku recheck confirmed Essential-0 $5/month and no dynos on either cloud app.
No UI changes, so browser QA is not repeated. No paid AI/Stars calls made.

Not completed: bot PostgreSQL outbox, managed attachment to bot, Doppler migration,
Sentry/privacy filters, OIDC credentials, domain/ACM, app deployment and live cutover.
Known limits: serialized Core transactions; crash-reserved credit recovery still
operator-mediated; no cloud availability/latency/payment acceptance claimed.
Rollback before deployment: keep the current live runtime, do not drop the database.
After migration release, never edit applied SQL or automatically downgrade schema.
Exact next step after usage reset: implement/test durable PostgreSQL payment outbox
in C:\student-ai-bot, preserve its existing owner edits/assets, attach the SAME
database (no second add-on), and prove outage/restart/idempotent delivery with worker=0.
Only after that continue the remaining gates in STAGING_RUNBOOK.md.

## 2026-09-04 — Durable outbox coordinated checkpoint

Bot 6c6d425 adds PostgreSQL-only bot_outbox persistence, preserving local SQLite and
legacy bridge-OFF. It does not directly mutate Core business state. Core CI now pins
that revision and checks real PostgreSQL outbox -> signed transport -> PostgreSQL Core.
Synthetic response loss AFTER Core commit leaves pending outbox; restart/concurrent
retries and a duplicate payment still yield exactly one payment row and one credit.
Full Core suite 103 passed; new real-Heroku cross-project regression 1 passed (existing
27 PostgreSQL tests unchanged, independently rerun in CI). Bot suite 79 tests with
3 expected PG skips; dedicated real-Heroku/SQLite outbox suite 6 passed, including
abrupt child-process termination after durable enqueue. No real payment/AI/polling.
Bot's pre-existing branding edits and untracked assets/outputs remain untouched.
Next: Doppler configuration, same-DB attachment, deployment and remaining runbook gates.

Infrastructure checkpoint: bot 6c6d425 and Core 933fe84 both GitHub CI GREEN (including
both PostgreSQL jobs). Attached existing postgresql-animate-45477 to the bot app as
DATABASE, release v3; no second database/paid resource. Created Doppler projects
student-os and student-ai-bot, each with default stg config. No runtime secrets read
or copied yet, no Heroku integration authorized, no code deployment/live polling.

External authorization gate: Doppler's Heroku OAuth page requests identity read and
write-protected access to ALL Heroku apps/resources including config vars/secrets.
This is broader than the two Student apps. Allow was NOT clicked; owner confirmation
required before granting it. Do not interpret migration authorization as approval for
this account-wide security grant. Next exact action: obtain owner decision on that
grant (or use a narrower manually controlled sync), then continue Doppler safely.
Do not touch yujiodoublex-factory. All prior bot owner changes/assets remain uncommitted.

## 2026-09-04 — Doppler Heroku sync configured

Owner explicitly approved the account-wide OAuth grant and completed Allow manually
after browser automation could not operate the Heroku approval page. Doppler connection
1bee42c0-bccc-4f8d-8ffe-7398eba5c5d3 verified Enabled. Created exactly these two syncs:
student-os/stg -> student-os-ernar-beta; student-ai-bot/stg -> student-ai-bot-ernar-beta.
Both show In Sync. Import options None for each: no Heroku config import into Doppler.
Post-sync read-only verification found DATABASE_URL plus only DOPPLER_CONFIG,
DOPPLER_ENVIRONMENT and DOPPLER_PROJECT on both apps. Bot has no dynos.
No runtime credentials migrated, no deployment, no new paid resource, no other sync.

Official Doppler CLI 3.76.5 installed through winget (installer hash verified).
Executable: %LOCALAPPDATA%/Microsoft/WinGet/Packages/Doppler.doppler_Microsoft.Winget.Source_8wekyb3d8bbwe/doppler.exe.
CLI login with scope limited to the Core checkout generated an authorization code
but did not open a page in the available browser. All auth output was suppressed;
pending attempts interrupted. Read-only projects command confirms no CLI token yet.
Next: owner performs one-time doppler login scoped to the Core checkout, keeping
codes/tokens out of chat. Then allowlisted local credentials -> Doppler stg configs
directly in memory; never upload entire .env or managed DATABASE_URL. Continue deploy.

## 2026-09-04 — Independent migration work while owner is away

Doppler CLI login explicitly BLOCKED_BY_OWNER. No repeated login/audit, no runtime
secret migration, no config-var or existing In Sync integration changes. DATABASE_URL
untouched. No live bot restart/cutover and no additional paid resources.

Core: Python 3.12 pin/slug exclusions, production ASGI entrypoint with optional generic
error reporting. Both apps: environment-only preflight with no dotenv/DB/network and
key-name-only failures; opt-in Sentry reconstructs category-only events, disables auto
integrations/PII/tracing/stack/local capture. Real SDK memory-transport privacy tests
prove hostile request/header/user/homework/exception data is excluded; no live Sentry
project/DSN configured. CI pins bot 57c205a: cloud-only fail-closed worker and durable
Eco background backoff, including storage-backed retry regression.

Domain preparation: enabled free Eco ACM. CLI 7.53.0 domain create failed because it
omits required sni_endpoint; no domain was created by those attempts. Bounded official
API call with existing Heroku authentication and null SNI added only student-os.dev.
Actual DNS target triangular-quince-o3z6hou8rvdwxkc3dcna64jv.herokudns.com; pending DNS.
DNS deliberately unchanged until Core runtime is configured/healthy. No certificate
issuance or working public HTTPS claimed. No auth credentials emitted/stored.

TEST/ATTACK: Core full suite with current bot root 109 passed, 25 expected PG skips;
real-Heroku PostgreSQL outbox -> Core ambiguous-commit regression 1 passed in 70s;
bot full suite 89 tests/4 PG skips, separate pre-existing real persistence cases 6
passed in 132s. PostgreSQL backoff coverage added to dedicated CI. Compile, staged
secret-pattern and diff checks plus Node PWA runtime checks pass. No UI change, so
no redundant local browser check. Real HTTPS/BrowserStack remains not executed.

CLOUD_READINESS_CHECKPOINT.md contains exact domain/config boundaries, five-part
HTTPS/device acceptance matrix, ordered deploy/rollback and exact owner login command.
Core deploy/runtime/OIDC/cloud synthetic/real-device acceptance BLOCKED_BY_DOPPLER_LOGIN
or absent external credentials. Next: verify bot build with worker=0 where possible,
record CI/deployment results; after owner login migrate allowlisted secrets directly
to existing stg configs and preflight Core before web deployment. Never enable polling.

Final external checkpoint: Core code 29393cf CI run 33870953687 GREEN (test + postgres);
bot 57c205a run 33870851244 GREEN (tests + postgres-outbox, including persisted backoff).
Bot tested commit deployed successfully to existing Heroku app as release v5, Python
3.12.14 / worker-only Procfile. Explicit worker=0:Eco applied; ps confirmed No dynos.
No worker polling or local restart. Core not deployed because runtime credentials are
still missing. Domain pending DNS/ACM issuance, not a working HTTPS app. DEVLOG and
checklist are the handoff; no further independent deployment action is safe now.
Core clean after commit; bot retains only the owner's original branding/assets/outputs.
Exact next action is owner login in CLOUD_READINESS_CHECKPOINT.md, then migrate only
allowlisted credentials via existing syncs and preflight/deploy Core with worker=0.

## 2026-09-04 — PRE-DEPLOY credentials checkpoint (bounded low-usage step)

Owner completed Doppler login/setup and authorized only credential migration/preflight,
explicitly NOT Core deploy, DNS change or live cutover. Read local .env sources only
into memory with interpolation disabled. No secret values in stdout, files or Git.
Migrated existing TELEGRAM_BOT_TOKEN to both existing stg configs; OPENAI_API_KEY and
OPENAI_MODEL to Core only. Allowlisted owner/support and fail-closed runtime settings
configured. Generated fresh 384-bit bridge secret in memory: Core BOT_BRIDGE_SECRET
and Bot STUDENT_OS_BRIDGE_SECRET match; no old local bridge secret reused.

Both existing Heroku syncs remain enabled and status=synced, confirmed via Doppler API:
Core lastSyncedAt 2026-09-04T12:51:37.533Z; Bot 2026-09-04T12:51:38.398Z.
Verified all migrated values equal destination Heroku values without printing values.
DATABASE_URL absent from Doppler and unchanged byte-for-byte in both Heroku apps;
all unrelated pre-existing Heroku config vars preserved. No sync recreation/import.

Environment-only preflight on actual destination configs: Bot PASS; Core BLOCKED by
missing TELEGRAM_CLIENT_ID, TELEGRAM_CLIENT_SECRET, TELEGRAM_REDIRECT_URI. These do not
exist in authorized local sources; no invented credentials or placeholder success.
Preflight regression tests 2 passed; cache-write warning only, no application failure.
No worker/one-off runtime started. Formation verified zero; latch explicitly false.
Core deploy NOT started. Bot retains previously built artifact, zero workers. DNS
unchanged; no live Telegram cutover or paid resource. No production acceptance claimed.

STOP. Exact next step after 5h reset: obtain/register missing Telegram OIDC credentials
through the official authorized flow (owner action if required), save to existing Core
stg config and rerun preflight. Only then continue Core deployment/readiness with bot
worker=0. Earlier login blocker is resolved; OIDC configuration is the remaining gate.
Core tracked tree clean after this docs-only checkpoint; bot's original owner edits
and assets/outputs remain untouched. No further atomic unit started at low usage.

## 2026-09-04 — OIDC owner step resolved; independent monitoring hardening

Resumed Core 96243bd / bot 0284aa8 without repeating PostgreSQL/outbox architecture work.
Official Telegram flow verified at https://core.telegram.org/bots/telegram-login:
BotFather mini app -> existing bot -> Login Widget -> Allowed URLs and separate Client
ID/Secret. Owner completed the requested direct Doppler configuration, not chat transfer.
Read-only actual destination preflight now has no missing/invalid fields; exact HTTPS
callback and owner ID match, all Doppler values match Heroku. DATABASE_URL remains only
Heroku-managed. APP_ENV is still staging, so production preflight gate is NOT satisfied.
Action review rejected the requested production-mode write; no write/deploy performed.
Explicit owner confirmation requested for production mode and Core deployment.

Sentry: existing authorized Education organization yujio2x had no projects. Created
student-os error-only project; logging/tracing/profiling/metrics not selected. New DSN
was kept in browser memory and entered in an unsaved Core Doppler form, never printed
or written to local files. Action review blocked Save pending explicit authorization
for this new credential. No SENTRY_DSN saved, no real synthetic event sent, no Bot Sentry
project created yet. Core/Bot DSN storage and synthetic-event permission requested.

Independent code fix: Sentry scrubber formerly discarded environment/service metadata.
Now preserves only fixed safe labels and rejects unhashable categories without leaking
data. Tests use real SDK memory transport; no user content leaves the process. Core
full suite 110 passed / 25 expected PG skips; focused OIDC/cloud/privacy 11 passed.
Bot config preflight passed on real one-off Eco runtime, no polling; optional deployed
storage probe added in bot source pending release. No local bot restart, DNS switch,
Core deployment or cutover. Owner branding/assets remain preserved in bot checkout.
## 2026-09-04 — Authorized production deployment and isolated monitoring smoke

Final cloud verification for this checkpoint:
- Core 1406110 deployed v10; Bot 98ad33f deployed v10. Bot push connection reset
  during build, but read-only release inspection proved deployment succeeded; no
  duplicate build was submitted. Core Eco web up; Bot has NO dynos after one-offs.
- GitHub CI green: Core 33895894959, Bot 33895845553 (including real PG CI jobs).
- Doppler API: exactly the two existing stg syncs enabled/status=synced. Actual
  destination values match all source values. DATABASE_URL excluded from Doppler.
- One synthetic event per service sent from finished Heroku one-off processes:
  Core 88b87b6ff1054d78bbaba203bf5727ae, issue 144972255;
  Bot fe62a8e76d534ceda0f5772540f24c31, issue 144972114.
  Both arrived in Sentry UI, production environment, fixed service/category tags,
  zero users, no assignment/AI text, request, cookies, auth payload or exception
  stack. SDK regression proves allowlisted outbound envelope. Sentry adds its own
  trace context and Heroku egress geography (Dublin); this is not end-user identity.
  Full raw server-normalized JSON was not separately audited/downloaded.
- Exactly one short real cloud AI submission passed live mode, how_to_defend and
  consumption of first free trial. No real Stars/Telegram API calls. Bridge response
  does not expose token counts (reported None); no additional AI calls made to measure.
- Public Heroku HTTPS browser loads Telegram-only login gate. Auth options show
  development_login=false; dev-login 404, unauthenticated admin/session 401.
- Actual HTML manifest URL /static/manifest.webmanifest HTTP 200 (root /manifest
  is not a route); scope/start_url '/', standalone, icons and root /sw.js HTTP 200.
  PWA runtime regression passed; service worker allowlist excludes all /api and
  /admin traffic. No installation/standalone/offline-device claim from this check.
- Local cloud acceptance used the real Bot adapter against Heroku HTTPS Core; it
  is not a custom-domain or cloud-worker-origin test. Restart proof is process-cold,
  not actual idle-sleep wake timing. These distinctions remain explicit.

Remaining acceptance is NOT declared green: DNS/ACM custom-domain routing, real OIDC
callback/login, verified owner admin, authenticated BrowserStack flows, real-device
PWA install/offline, and final live bot cutover. DNS and cutover are explicitly held
by owner; do not bypass login, enable dev auth, start polling, or purchase resources.
Next exact gated step: after separate owner permission to change DNS, point only
student-os.dev to the already assigned Heroku target, verify ACM/HTTPS, then perform
real OIDC and authenticated device QA. Keep worker=0 throughout these checks.
If DNS remains on hold, do not claim custom-domain beta or final cutover readiness.


Owner explicitly authorized Core production mode/deployment and Sentry DSN storage
in both existing Doppler stg configs. Latest restrictions: no DNS changes, no live
Telegram cutover, cloud worker stays zero. No new resources/plans were provisioned.
Production config preflight passed (secure cookies, dev login/admin off, Core ledger,
OIDC fields present and matching expected callback). DATABASE_URL is unchanged and
Heroku-managed only. Core 233513e built/released as v9: Eco web up, health HTTP 200.
Bot fb64c2e built/released as v8; subsequent config releases may advance release IDs.
Bot one-off --storage preflight passed CLOUD_IMPORTS_AND_POSTGRES_OUTBOX_OK_NO_POLLING.
Both existing Sentry error-only projects now have DSNs saved directly to Doppler,
with production environment and no replay/tracing/default integrations or PII enabled.

Added explicit python -m app.monitoring_smoke core|bot for one constant synthetic
event with bounded flush and generic failure output. Event ID is correlation only,
not delivery evidence; Sentry UI verification is required. No app/polling import.
Regression: Core 112 passed / 25 expected PG skips; Bot 93 tests / 4 PG skips.
New smoke tests cover constant payload, bounded flush, missing config, private errors.
Cloud acceptance runner in Bot confines writes to unique synthetic identity/payment,
targets only the two approved apps, reads credentials in memory, and restarts Core
only with explicit --exercise. It never retries unrelated pending outbox records.
Actual signed health/catalog and six auth-negative checks passed. Synthetic lost
response after committed payment, durable outbox reopen/retry and exactly-once credit
passed. Evidence run: 57dffbbafb414bfc84c5b86ba9daff40. Core restart then passed:
same user ID, payment row count one, balance one, unchanged migration version/checksum/
applied_at. Catalog, entitlement and duplicate-payment delivery work after restart.
This is an actual process-cold/restart test, NOT proof of a 30-minute Eco sleep wake.
Custom-domain OIDC/browser/admin proof remains blocked by owner's explicit DNS hold.
No local bot restart and no cloud polling were performed; owner edits stay untouched.
## 2026-09-04 — Owner-authorized DNS / ACM / OIDC entry

Owner explicitly authorized apex DNS to the current Heroku target, keeping Bot=0,
no cutover and no purchases. Name.com login required owner CAPTCHA/device-email
confirmation; completed by owner. DNS table contained no user-created records.
Added ONE ANAME, empty host (student-os.dev), TTL 300, target confirmed again by
Heroku domains output: triangular-quince-o3z6hou8rvdwxkc3dcna64jv.herokudns.com.
No records deleted, no nameserver changes. Saved Name.com record ID 288468758.
Authoritative ns1bcp.name.com plus 1.1.1.1 and 8.8.8.8 returned Heroku addresses.
ACM refresh completed: Cert issued, Let's Encrypt YR2, SAN student-os.dev,
expires 2026-12-03. Python default trust/hostname validation passed TLS 1.3;
https://student-os.dev/api/health HTTP 200. No certificate-warning bypass.

Real browser OIDC reached official Telegram authorization for TaskMentorBot and
existing owner account; Continue sent owner an in-app confirmation. Awaiting owner
confirmation before calling OIDC/admin successful; no codes or auth tokens requested.
Bot inspection: no dynos. Unauthenticated custom-domain admin correctly returns 401.

Cloud smoke found HTTP served 200 instead of redirect. Added Heroku-only HTTPS
boundary, enabled only with DYNO plus staging/production, preserving local mode.
Heroku overwrites X-Forwarded-Proto (official guidance):
https://help.heroku.com/J2R1S4T8/can-heroku-force-an-application-to-use-ssl-tls
Redirect uses configured HTTPS callback origin, not attacker Host; preserves path/query
and method via 307/no-store. HTTPS is passed through without a redirect loop. Tests
cover spoofed Host, missing/ambiguous proto, path/query and HTTPS pass-through.
Validation: full Core suite 114 passed / 25 expected PG skips; compile/diff/staged
secret-pattern checks passed. Core d2cf2a7 pushed, CI 33901025793 successful, Heroku
release v11 successful. Actual http://student-os.dev/ -> 307 https://student-os.dev/;
both custom-domain and Heroku-origin HTTPS health 200, no redirect loop. Working tree
clean after checkpoint; Bot source/runtime unchanged (worker=0). OIDC owner in-app
confirmation still pending; do not call login/admin verified. Next: confirm Telegram,
then inspect real callback/session/owner admin without logging session/CSRF values.
## 2026-09-04 — Low-usage pre-cutover authentication gate

Fresh owner confirmation arrived promptly, but browser again returned to login gate.
Read-only DB now shows zero login attempts (state consumed) and owner identity still
absent. This invalidates expiry as explanation for the FRESH attempt: failure is after
consume, in code exchange/token verification (exact reason not yet established).
Current exception mapping hides safe diagnostic stage. Do not change signature,
audience, issuer, expiry, PKCE or owner checks to make this pass. Next bounded unit
after verified reset: add/test strictly allowlisted failure-stage diagnostics without
logging code/state/token/profile/secrets, then determine exchange versus JWKS/JWT
failure using real runtime; obtain owner confirmation only if a new real flow needs it.
Official Telegram manual flow matches current endpoint/auth/PKCE contract and documents
RS256 as default; there is no evidence yet for changing algorithm or credentials.
Successful callback, owner admin, logout/relogin and real replay remain NOT verified.

Owner reported Telegram confirmation and authorized a conditional post-reset overnight
run, maximum about four hours, cutover ONLY after every critical gate passes. Before
reset keep cloud worker zero and legacy polling unchanged. No new paid/legal/access
actions, real Stars payment, destructive user-data deletion or irreversible migration.

Actual browser returned to login gate, not authenticated settings. Read-only production
DB check: owner Telegram identity 8247777174 absent; two expired login attempts exist.
Therefore previous real callback/login cannot be marked successful (consistent with
five-minute state expiry). Owner config matches exactly; DEV_LOGIN_ENABLED=false and
DEV_ADMIN_ENABLED=false. No bypass, identity fabrication or role promotion attempted.
Started one fresh real Telegram authorization attempt and requested immediate owner
in-app confirmation. Pending gates: callback, verified owner identity/admin, real
logout/relogin and replay/state checks. Local OIDC/HTTPS regression: 6 passed.

Usage read: 91% consumed, 9% remaining; reset at 2026-09-04 21:00:01 UTC (02:00 local).
Do not start a risky unit before fresh budget is verified. No overnight continuation
has been scheduled yet while a fresh owner authentication action remains unresolved.
Exact next step: confirm the newest Telegram request within five minutes; inspect
callback and verify the owner's persisted identity/role without logging credentials.
If that request expires, start a new browser login with owner present; never extend or
bypass state expiry just to pass the gate. Worker=0 and no cutover until all gates green.
## 2026-09-05 — Safe OIDC failure-stage instrumentation

Fresh five-hour budget verified at 95% remaining before overnight work. Repository and
CI truth: Core 38cccd0 clean and CI 33902518210 green; Bot 6a6fdd2 retains only the
known owner branding/assets/output changes. Cloud Bot remains zero; legacy bot intact.

Implemented privacy-preserving OIDC diagnostics for the unresolved real callback.
Only two constant allowlisted Sentry categories can leave the process:
oidc_exchange_failed (HTTP/token response stage) or oidc_verify_failed (JWKS/JWT
validation stage). No status body, URL, code, state, verifier, token, claim/profile,
cookie, session, CSRF, header, exception text or local variable is attached. Existing
Sentry reconstruction still drops every non-allowlisted event surface. Validation
semantics (RS256, issuer, audience, exp/iat, numeric positive ID, PKCE and one-time
state) are unchanged. Focused privacy/OIDC tests: 8 passed. First test failure was a
fixture using a non-httpx constructor exception; corrected to httpx.ConnectError and
rerun green. Full suite and live deployment follow this entry.

Full Core suite: 115 passed / 25 expected PostgreSQL skips, with the one known
Starlette/httpx deprecation warning. Compile and diff checks passed. Commit 17c5f91
was pushed; GitHub Actions run 33919636246 completed successfully. Heroku deployed
the exact commit as Core release v12; Eco web is up and the public
https://student-os.dev/api/health endpoint returns 200. ACM remains issued and trusted
through 2026-12-03; HTTP still redirects to the configured HTTPS origin with 307.

Public PWA preflight passed over the custom domain: manifest 200 with Student OS,
standalone display, root start URL and three icons; root service worker 200 with the
expected JavaScript content type. BrowserStack authenticated successfully and started
a real Samsung Galaxy S24 / Android 14 / Chrome session. Its remote-device address
bridge accepted the URL into the control field but did not dispatch navigation, so no
claim is made for rendered mobile UI or authenticated device QA from this run. Do not
substitute this partial session for the still-required real-device login/install proof.

The deployed diagnostics require one new real callback to identify exchange versus
JWKS/JWT verification failure. The owner is unavailable during this overnight run, so
the callback, persisted Telegram identity 8247777174, production admin, logout/relogin
and real replay/state gates remain red. No validation was weakened and no identity was
fabricated. Consequently live cutover was not performed. Bot Heroku app still reports
no dynos (worker=0), and the legacy live bot was not stopped or modified. No DNS,
database, paid-resource or secret changes were made. Exact next step with the owner
present: start one fresh Telegram login and confirm it within five minutes, then inspect
Sentry for exactly one allowlisted stage category and fix only the proven stage before
rerunning identity/admin/session/replay gates.
