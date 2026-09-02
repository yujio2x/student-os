from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.ai_service import StudyService
from app.config import Settings, load_settings
from app.database import Database


LOCAL_USER = "local-demo-user"
ALLOWED_FIELDS = {"room", "teacher", "lesson_type", "group_name", "notes"}


class StudyRequest(BaseModel):
    assignment: str = Field(min_length=3, max_length=12_000)
    subject: str = Field(default="", max_length=120)
    title: str = Field(default="", max_length=160)

    @field_validator("assignment")
    @classmethod
    def assignment_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("assignment must contain visible text")
        return value.strip()


class DeadlineCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    subject: str = Field(default="", max_length=120)
    due_at: datetime
    description: str = Field(default="", max_length=4000)
    source: str = Field(default="manual", pattern="^(manual|ai-study)$")

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must contain visible text")
        return value.strip()


class CompletionUpdate(BaseModel):
    completed: bool


class PreferencesUpdate(BaseModel):
    theme: str = Field(pattern="^(light|dark)$")
    schedule_view: str = Field(pattern="^(week|day)$")
    mobile_schedule_view: str = Field(pattern="^(week|day)$")
    visible_fields: list[str] = Field(max_length=5)

    @field_validator("visible_fields")
    @classmethod
    def known_fields_only(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(item not in ALLOWED_FIELDS for item in value):
            raise ValueError("visible_fields contains duplicates or unsupported values")
        return value


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or load_settings()
    database = Database(config.database_path)
    study = StudyService(config.openai_api_key, config.openai_model)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.initialize()
        database.seed_demo(LOCAL_USER)
        yield

    app = FastAPI(title="Student OS", version="0.1.0", lifespan=lifespan)
    app.state.database = database
    app.state.study = study

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "stage": "PROTOTYPE"}

    @app.get("/api/bootstrap")
    def bootstrap() -> dict:
        return {
            "lessons": database.lessons(LOCAL_USER),
            "deadlines": database.deadlines(LOCAL_USER),
            "preferences": database.preferences(LOCAL_USER),
            "ai_mode": "live" if study.client else "demo",
        }

    @app.post("/api/study/analyze")
    def analyze(payload: StudyRequest) -> dict:
        try:
            return study.analyze(payload.assignment, payload.subject, payload.title).to_dict()
        except Exception as exc:
            raise HTTPException(status_code=502, detail="AI analysis failed safely; no deadline was saved") from exc

    @app.post("/api/deadlines", status_code=201)
    def create_deadline(payload: DeadlineCreate) -> dict:
        return database.add_deadline(
            LOCAL_USER, payload.title, payload.subject.strip(),
            payload.due_at.isoformat(timespec="minutes"), payload.description.strip(), payload.source,
        )

    @app.patch("/api/deadlines/{deadline_id}")
    def update_deadline(deadline_id: int, payload: CompletionUpdate) -> dict:
        result = database.set_deadline_completed(LOCAL_USER, deadline_id, payload.completed)
        if result is None:
            raise HTTPException(status_code=404, detail="Deadline not found")
        return result

    @app.put("/api/preferences")
    def update_preferences(payload: PreferencesUpdate) -> dict:
        return database.update_preferences(
            LOCAL_USER, payload.theme, payload.schedule_view,
            payload.mobile_schedule_view, payload.visible_fields,
        )

    static_dir = Path(__file__).resolve().parent.parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app


app = create_app()
