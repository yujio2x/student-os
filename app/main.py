from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ai_service import StudyService
from app.auth import SESSION_COOKIE, SessionService
from app.config import Settings, load_settings
from app.database import (
    AdminActionConflict, Database, DeadlineConflictError, ExternalIdentityConflict,
    LessonConflictError,
)
from app.entitlements import LocalEntitlementService
from app.schedule_import import MAX_UPLOAD_BYTES, ScheduleImportError, ScheduleImportService
from app.telegram_auth import TelegramAuthError, TelegramLoginVerifier


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


class TelegramAuthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    first_name: str = Field(default="", max_length=160)
    last_name: str = Field(default="", max_length=160)
    username: str = Field(default="", max_length=80)
    photo_url: str = Field(default="", max_length=2048)
    auth_date: int = Field(gt=0)
    hash: str = Field(min_length=64, max_length=64)


class FeedbackInput(BaseModel):
    kind: str = Field(pattern="^(product|student-ai)$")
    rating: str = Field(default="", pattern="^(|positive|negative)$")
    message: str = Field(default="", max_length=2000)
    request_id: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def useful_feedback(self):
        self.message = self.message.strip()
        if self.kind == "product" and not self.message:
            raise ValueError("product feedback requires a message")
        if self.kind == "student-ai" and not self.rating:
            raise ValueError("Student AI feedback requires a rating")
        return self


class CreditAdjustment(BaseModel):
    delta: int = Field(ge=-1000, le=1000)
    reason: str = Field(min_length=3, max_length=500)
    request_id: str = Field(min_length=8, max_length=128)

    @field_validator("delta")
    @classmethod
    def nonzero_delta(cls, value: int) -> int:
        if value == 0:
            raise ValueError("delta must not be zero")
        return value


class UnlimitedAdjustment(BaseModel):
    enabled: bool
    reason: str = Field(min_length=3, max_length=500)
    request_id: str = Field(min_length=8, max_length=128)


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
    telegram = TelegramLoginVerifier(
        config.telegram_bot_token, config.telegram_auth_max_age_seconds
    )
    entitlements = LocalEntitlementService(database, config.entitlement_source)

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
    app.state.telegram = telegram
    app.state.entitlements = entitlements

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

    def admin_session(session: dict = Depends(current_session)) -> dict:
        if session["role"] != "admin":
            raise HTTPException(status_code=403, detail="Доступ администратора запрещён")
        return session

    def admin_csrf_session(
        request: Request, session: dict = Depends(admin_session)
    ) -> dict:
        supplied = request.headers.get("X-CSRF-Token", "")
        if not supplied or not secrets.compare_digest(supplied, session["csrf_token"]):
            raise HTTPException(status_code=403, detail="Недействительный CSRF-токен")
        return session

    def issue_browser_session(response: Response, user: dict, mode: str) -> dict:
        issued = sessions.issue(user["id"])
        response.set_cookie(
            SESSION_COOKIE, issued.token, max_age=config.session_ttl_hours * 3600,
            httponly=True, secure=config.secure_cookies, samesite="lax", path="/",
        )
        return {
            "user": {"id": user["id"], "display_name": user["display_name"], "role": user["role"]},
            "csrf_token": issued.csrf_token, "expires_at": issued.expires_at, "mode": mode,
        }

    @app.post("/api/auth/dev-login")
    def development_login(request: Request, response: Response) -> dict:
        if config.environment == "production" or not config.dev_login_enabled:
            raise HTTPException(status_code=404, detail="Not found")
        user = database.ensure_local_user()
        sessions.revoke(request.cookies.get(SESSION_COOKIE))
        return issue_browser_session(response, user, "development")

    def verify_telegram_payload(payload: TelegramAuthPayload) -> dict:
        try:
            verified = telegram.verify(payload.model_dump())
        except TelegramAuthError as exc:
            status = 503 if not config.telegram_bot_token else 401
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        if not database.consume_telegram_auth(verified["replay_key"]):
            raise HTTPException(status_code=409, detail="Данные Telegram уже использованы")
        return verified

    @app.post("/api/auth/telegram/login")
    def telegram_login(payload: TelegramAuthPayload, request: Request, response: Response) -> dict:
        verified = verify_telegram_payload(payload)
        user = database.telegram_login_user(
            verified["telegram_id"], verified["username"], verified["display_name"]
        )
        if config.admin_telegram_id and secrets.compare_digest(
            verified["telegram_id"], config.admin_telegram_id
        ):
            database.set_user_role(user["id"], "admin")
            user["role"] = "admin"
        sessions.revoke(request.cookies.get(SESSION_COOKIE))
        return issue_browser_session(response, user, "telegram")

    @app.post("/api/account/telegram/link")
    def link_telegram(
        payload: TelegramAuthPayload, session: dict = Depends(csrf_session)
    ) -> dict:
        verified = verify_telegram_payload(payload)
        try:
            identity = database.link_telegram_identity(
                session["user_id"], verified["telegram_id"],
                verified["username"], verified["display_name"],
            )
        except ExternalIdentityConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"linked": True, "username": identity["username"], "linked_at": identity["linked_at"]}

    @app.delete("/api/account/telegram/link")
    def unlink_telegram(session: dict = Depends(csrf_session)) -> dict:
        if database.telegram_identity(session["user_id"]) is None:
            raise HTTPException(status_code=404, detail="Telegram-аккаунт не связан")
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить единственный production-вход без способа восстановления",
        )

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
            "telegram": {
                "configured": bool(config.telegram_bot_token),
                "identity": database.telegram_identity(user_id),
            },
            "student_ai_entitlement": entitlements.get_balance(user_id),
        }

    @app.post("/api/feedback", status_code=201)
    def submit_feedback(payload: FeedbackInput, session: dict = Depends(csrf_session)) -> dict:
        result = database.record_feedback(
            session["user_id"], payload.kind, payload.rating, payload.message, payload.request_id
        )
        if result.pop("created"):
            database.record_event(session["user_id"], "feedback_sent", payload.kind)
        return result

    @app.post("/api/study/analyze")
    def analyze(payload: StudyRequest, session: dict = Depends(csrf_session)) -> dict:
        try:
            result = study.analyze(payload.assignment, payload.subject, payload.title).to_dict()
            database.record_event(session["user_id"], "student_ai_used")
            return result
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
        database.record_event(session["user_id"], "schedule_imported", str(len(lessons)))
        return {"lessons": lessons, "imported": len(lessons)}

    @app.post("/api/deadlines", status_code=201)
    def create_deadline(payload: DeadlineCreate, session: dict = Depends(csrf_session)) -> dict:
        deadline = database.add_deadline(
            session["user_id"], payload.title, payload.subject.strip(),
            payload.due_at.isoformat(timespec="minutes"), payload.description.strip(), payload.source,
        )
        database.record_event(session["user_id"], "deadline_created", str(deadline["id"]))
        return deadline

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

    @app.get("/api/admin/overview")
    def admin_overview(session: dict = Depends(admin_session)) -> dict:
        return {**database.admin_overview(), "entitlement_connected": config.entitlement_source == "local"}

    @app.get("/api/admin/users")
    def admin_users(
        q: str = "", limit: int = 20, offset: int = 0,
        session: dict = Depends(admin_session),
    ) -> dict:
        if len(q) > 120 or not 1 <= limit <= 100 or offset < 0:
            raise HTTPException(status_code=422, detail="Некорректная пагинация")
        return database.admin_users(q, limit, offset)

    @app.get("/api/admin/users/{user_id}")
    def admin_user(user_id: str, session: dict = Depends(admin_session)) -> dict:
        result = database.admin_user(user_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        result["actions"] = database.admin_actions(user_id, 20, 0)["actions"]
        return result

    @app.get("/api/admin/feedback")
    def admin_feedback(
        limit: int = 50, offset: int = 0, session: dict = Depends(admin_session)
    ) -> dict:
        if not 1 <= limit <= 100 or offset < 0:
            raise HTTPException(status_code=422, detail="Некорректная пагинация")
        return database.admin_feedback(limit, offset)

    @app.get("/api/admin/actions")
    def admin_actions(
        limit: int = 50, offset: int = 0, session: dict = Depends(admin_session)
    ) -> dict:
        if not 1 <= limit <= 100 or offset < 0:
            raise HTTPException(status_code=422, detail="Некорректная пагинация")
        return database.admin_actions(None, limit, offset)

    def require_connected_entitlements() -> None:
        if config.entitlement_source != "local":
            raise HTTPException(status_code=409, detail="Источник credits пока не подключён")

    @app.post("/api/admin/users/{user_id}/credits")
    def adjust_credits(
        user_id: str, payload: CreditAdjustment,
        session: dict = Depends(admin_csrf_session),
    ) -> dict:
        require_connected_entitlements()
        if database.admin_user(user_id) is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        entitlements.get_balance(user_id)
        try:
            balance = database.admin_adjust_credits(
                session["user_id"], user_id, payload.delta, payload.reason.strip(), payload.request_id
            )
        except AdminActionConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if balance is None:
            raise HTTPException(status_code=409, detail="Баланс не может стать отрицательным")
        return {"balance": balance}

    @app.post("/api/admin/users/{user_id}/unlimited")
    def set_unlimited(
        user_id: str, payload: UnlimitedAdjustment,
        session: dict = Depends(admin_csrf_session),
    ) -> dict:
        require_connected_entitlements()
        if database.admin_user(user_id) is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        entitlements.get_balance(user_id)
        try:
            enabled = database.admin_set_unlimited(
                session["user_id"], user_id, payload.enabled,
                payload.reason.strip(), payload.request_id,
            )
        except AdminActionConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if enabled is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return {"unlimited": enabled}

    static_dir = Path(__file__).resolve().parent.parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/admin", include_in_schema=False)
    def admin_page(session: dict = Depends(admin_session)) -> FileResponse:
        return FileResponse(static_dir / "admin.html")

    return app


app = create_app()
