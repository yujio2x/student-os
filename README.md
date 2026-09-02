# Student OS

Status: **WORKING MVP** (local v0.1 vertical slice)

Student OS is a web-first student workspace. The v0.1 vertical slice connects a weekly schedule, assignment analysis, a first-class "How to Defend" guide, editable deadlines, and a calendar.

## What works

- responsive Today dashboard with next-class and deadline summaries;
- week/day schedule with configurable visible fields;
- light and dark themes persisted in SQLite;
- text assignment analysis with a structured explanation, checks, and first-class "How to Defend" section;
- editable AI deadline suggestion that is never auto-saved;
- calendar display and deadline completion toggle;
- local deterministic study demo when no API key is configured;
- critical API/adversarial tests and GitHub Actions CI.

## Run locally

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python run.py
```

Open `http://127.0.0.1:8000`.

Run tests:

```powershell
.\.venv\Scripts\python -m pytest tests -q
```

## Project structure

- `app/` - web API, application/domain services, persistence, and AI integration
- `static/` - responsive web client
- `tests/` - critical flow and adversarial checks
- `docs/DEVLOG.md` - detailed engineering source of truth

## Configuration

Copy `.env.example` to `.env` locally. Never commit `.env`.

`OPENAI_API_KEY` is optional for the local deterministic study demo and required for live AI responses. The live integration uses the Responses API with a strict JSON schema and `store=False`.

## Known limitations

This is a single-user local MVP, not production. Authentication and real user isolation are not implemented. Schedule editing UI, assignment history, file/PDF/image input, recurring schedules, time zones, Directory, Library, payments, Telegram adapter, PWA installability, and native apps remain outside this checkpoint. The live AI path requires the user's own API key and was contract-checked but not billed/tested against the API during this session.
