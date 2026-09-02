# Student OS

Status: **PROTOTYPE**

Student OS is a web-first student workspace. The v0.1 vertical slice connects a weekly schedule, assignment analysis, a first-class "How to Defend" guide, editable deadlines, and a calendar.

## Current state

The repository foundation and migration audit exist. Product features are being implemented and are not yet claimed as working.

## Planned v0.1 structure

- `app/` - web API, application/domain services, persistence, and AI integration
- `static/` - responsive web client
- `tests/` - critical flow and adversarial checks
- `docs/DEVLOG.md` - detailed engineering source of truth

## Configuration

Copy `.env.example` to `.env` locally. Never commit `.env`.

`OPENAI_API_KEY` is optional for the local deterministic study demo and required for live AI responses.

## Known limitations

The initial foundation is not yet a working Student OS vertical slice. Authentication, file uploads, Directory, Library, payments, and native apps are outside v0.1.
