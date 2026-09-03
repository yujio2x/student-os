from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from app.ai_service import StudyService
from app.auth import SESSION_COOKIE, SessionService
from app.config import Settings, load_settings
from app.database import Database, DeadlineConflictError, LessonConflictError
from app.schedule_import import MAX_UPLOAD_BYTES, ScheduleImportError, ScheduleImportService


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


class DeadlineUpdate(DeadlineCreate):
    completed: bool
    source: str = Field(default="manual", exclude=True)


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


class LessonInput(BaseModel):
    weekday: int = Field(ge=0, le=6)
    subject: str = Field(min_length=1, max_length=120)
    starts_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    ends_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    room: str = Field(default="", max_length=80)
    location: str = Field(default="", max_length=120)
    teacher: str = Field(default="", max_length=120)
    lesson_type: str = Field(default="", max_length=80)
    group_name: str = Field(default="", max_length=80)
    notes: str = Field(default="", max_length=1000)

    @field_validator("subject")
    @classmethod
    def subject_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("subject must contain visible text")
        return value.strip()

    @field_validator("room", "location", "teacher", "lesson_type", "group_name", "notes")
    @classmethod
    def trim_optional_fields(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def valid_time_range(self):
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must be earlier than ends_at")
        return self

    def record(self) -> dict:
        return self.model_dump()


class ImportConfirm(BaseModel):
    lessons: list[LessonInput] = Field(min_length=1, max_length=100)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or load_settings()
    database = Database(config.database_path)
    sessions = SessionService(database, config.session_ttl_hours)
    study = StudyService(config.openai_api_key, config.openai_model)
    schedule_import = ScheduleImportService(config.openai_api_key, config.openai_model)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.initialize()
        if config.environment != "production" and config.dev_login_enabled:
            local_user = database.ensure_local_user()
            database.seed_demo(local_user["id"])
        yield

    app = FastAPI(title="Student OS", version="0.1.0", lifespan=lifespan)
    app.state.database = database
    app.state.study = study
    app.state.schedule_import = schedule_import
    app.state.sessions = sessions

    def current_session(request: Request) -> dict:
        session = sessions.resolve(request.cookies.get(SESSION_COOKIE))
        if session is None:
            raise HTTPException(status_code=401, detail="Требуется вход")
        return session

    def csrf_session(request: Request, session: dict = Depends(current_session)) -> dict:
        supplied = request.headers.get("X-CSRF-Token", "")
        if not supplied or not secrets.compare_digest(supplied, session["csrf_token"]):
            raise HTTPException(status_code=403, detail="Недействительный CSRF-токен")
        return session

    @app.post("/api/auth/dev-login")
    def development_login(request: Request, response: Response) -> dict:
        if config.environment == "production" or not config.dev_login_enabled:
            raise HTTPException(status_code=404, detail="Not found")
        user = database.ensure_local_user()
        sessions.revoke(request.cookies.get(SESSION_COOKIE))
        issued = sessions.issue(user["id"])
        response.set_cookie(
            SESSION_COOKIE, issued.token, max_age=config.session_ttl_hours * 3600,
            httponly=True, secure=config.secure_cookies, samesite="lax", path="/",
        )
        return {
            "user": {"id": user["id"], "display_name": user["display_name"], "role": user["role"]},
            "csrf_token": issued.csrf_token,
            "expires_at": issued.expires_at,
            "mode": "development",
        }

    @app.get("/api/auth/session")
    def auth_session(session: dict = Depends(current_session)) -> dict:
        return {
            "user": {"id": session["user_id"], "display_name": session["display_name"], "role": session["role"]},
            "csrf_token": session["csrf_token"], "expires_at": session["expires_at"],
        }

    @app.post("/api/auth/logout", status_code=204)
    def logout(request: Request, session: dict = Depends(csrf_session)) -> Response:
        sessions.revoke(request.cookies.get(SESSION_COOKIE))
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "stage": "PROTOTYPE"}

    @app.get("/api/bootstrap")
    def bootstrap(session: dict = Depends(current_session)) -> dict:
        user_id = session["user_id"]
        return {
            "lessons": database.lessons(user_id),
            "deadlines": database.deadlines(user_id),
            "preferences": database.preferences(user_id),
            "ai_mode": "live" if study.client else "demo",
            "session": {
                "user": {"id": user_id, "display_name": session["display_name"], "role": session["role"]},
                "csrf_token": session["csrf_token"], "expires_at": session["expires_at"],
            },
        }

    @app.post("/api/study/analyze")
    def analyze(payload: StudyRequest, session: dict = Depends(csrf_session)) -> dict:
        try:
            return study.analyze(payload.assignment, payload.subject, payload.title).to_dict()
        except Exception as exc:
            raise HTTPException(status_code=502, detail="AI analysis failed safely; no deadline was saved") from exc

    @app.post("/api/lessons", status_code=201)
    def create_lesson(payload: LessonInput, session: dict = Depends(csrf_session)) -> dict:
        try:
            return database.add_lesson(session["user_id"], payload.record())
        except LessonConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.put("/api/lessons/{lesson_id}")
    def update_lesson(lesson_id: int, payload: LessonInput, session: dict = Depends(csrf_session)) -> dict:
        try:
            result = database.update_lesson(session["user_id"], lesson_id, payload.record())
        except LessonConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="Занятие не найдено")
        return result

    @app.delete("/api/lessons/{lesson_id}", status_code=204)
    def delete_lesson(lesson_id: int, session: dict = Depends(csrf_session)) -> Response:
        if not database.delete_lesson(session["user_id"], lesson_id):
            raise HTTPException(status_code=404, detail="Занятие не найдено")
        return Response(status_code=204)

    @app.post("/api/schedule/import/preview")
    async def preview_schedule_import(
        file: UploadFile = File(...), session: dict = Depends(csrf_session)
    ) -> dict:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        await file.close()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Файл превышает лимит 6 МБ")
        try:
            lessons = app.state.schedule_import.extract(
                file.filename or "", file.content_type or "application/octet-stream", data
            )
        except ScheduleImportError as exc:
            status = 503 if "OPENAI_API_KEY" in str(exc) else 422
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail="Распознавание не завершено; расписание не изменено"
            ) from exc
        return {
            "lessons": lessons,
            "source": file.filename,
            "saved": False,
            "default_excluded_types": ["СРСП"],
            "notice": "Проверьте и исправьте все строки перед подтверждением",
        }

    @app.post("/api/schedule/import/confirm", status_code=201)
    def confirm_schedule_import(payload: ImportConfirm, session: dict = Depends(csrf_session)) -> dict:
        try:
            lessons = database.import_lessons(
                session["user_id"], [lesson.record() for lesson in payload.lessons]
            )
        except LessonConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"lessons": lessons, "imported": len(lessons)}

    @app.post("/api/deadlines", status_code=201)
    def create_deadline(payload: DeadlineCreate, session: dict = Depends(csrf_session)) -> dict:
        return database.add_deadline(
            session["user_id"], payload.title, payload.subject.strip(),
            payload.due_at.isoformat(timespec="minutes"), payload.description.strip(), payload.source,
        )

    @app.patch("/api/deadlines/{deadline_id}")
    def update_deadline(
        deadline_id: int, payload: CompletionUpdate, session: dict = Depends(csrf_session)
    ) -> dict:
        result = database.set_deadline_completed(session["user_id"], deadline_id, payload.completed)
        if result is None:
            raise HTTPException(status_code=404, detail="Deadline not found")
        return result

    @app.put("/api/deadlines/{deadline_id}")
    def replace_deadline(
        deadline_id: int, payload: DeadlineUpdate, session: dict = Depends(csrf_session)
    ) -> dict:
        try:
            result = database.update_deadline(
                session["user_id"], deadline_id, payload.title, payload.subject.strip(),
                payload.due_at.isoformat(timespec="minutes"), payload.description.strip(),
                payload.completed,
            )
        except DeadlineConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="Дедлайн не найден")
        return result

    @app.delete("/api/deadlines/{deadline_id}", status_code=204)
    def delete_deadline(deadline_id: int, session: dict = Depends(csrf_session)) -> Response:
        if not database.delete_deadline(session["user_id"], deadline_id):
            raise HTTPException(status_code=404, detail="Дедлайн не найден")
        return Response(status_code=204)

    @app.put("/api/preferences")
    def update_preferences(payload: PreferencesUpdate, session: dict = Depends(csrf_session)) -> dict:
        return database.update_preferences(
            session["user_id"], payload.theme, payload.schedule_view,
            payload.mobile_schedule_view, payload.visible_fields,
        )

    static_dir = Path(__file__).resolve().parent.parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app


app = create_app()
