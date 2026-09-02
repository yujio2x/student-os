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
commit: pending
branch: main
pushed: NO
purpose: safe repository foundation and documented migration audit
tests: pending scaffold checks
attack checks: pending staged secret scan
known limitations: feature implementation has not started

### Next technical step

Implement persistence and domain contracts for lessons, assignments, AI study results, and editable deadlines.

