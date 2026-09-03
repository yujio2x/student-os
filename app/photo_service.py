"""Adapter-independent photo setup/selection domain. Raw images are never persisted."""
from __future__ import annotations

import hashlib
import io
import json
import secrets
import time
import warnings

from PIL import Image, UnidentifiedImageError

from app.entitlements import ReservationConflict

MAX_PHOTO_BYTES = 6 * 1024 * 1024
MAX_PIXELS = 16_000_000


class PhotoError(ValueError):
    pass


def validate_photo(data: bytes, mime: str) -> None:
    if not data or len(data) > MAX_PHOTO_BYTES:
        raise PhotoError("Фото должно быть не больше 6 МБ")
    expected = {"image/jpeg": "JPEG", "image/png": "PNG"}.get(mime)
    if not expected or not ((expected == "PNG" and data.startswith(b"\x89PNG\r\n\x1a\n"))
                            or (expected == "JPEG" and data.startswith(b"\xff\xd8\xff"))):
        raise PhotoError("Допустимы настоящие PNG и JPEG")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format != expected or image.width * image.height > MAX_PIXELS or min(image.size) < 1:
                    raise PhotoError("Недопустимый размер изображения")
                if getattr(image, "n_frames", 1) != 1:
                    raise PhotoError("Анимация не поддерживается")
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise PhotoError("Изображение повреждено или слишком большое") from None


class PhotoService:
    def __init__(self, database, entitlements, engine):
        self.database, self.entitlements, self.engine = database, entitlements, engine

    def initialize(self):
        with self.database.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS photo_quotes (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    image_hash TEXT NOT NULL, source TEXT NOT NULL, amount INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL, claimed INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS photo_sessions (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    tasks TEXT NOT NULL, expires_at INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS photo_sessions_owner ON photo_sessions(user_id, expires_at);
                CREATE TABLE IF NOT EXISTS photo_requests (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    status TEXT NOT NULL, input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL);
            """)
        self.cleanup()

    def cleanup(self):
        with self.database.connection() as db:
            db.execute("DELETE FROM photo_sessions WHERE expires_at<=?", (int(time.time()),))
            db.execute("DELETE FROM photo_quotes WHERE expires_at<=?", (int(time.time()),))

    def quote(self, user_id, data, mime):
        validate_photo(data, mime)
        self.cleanup()
        state = self.entitlements.get_balance(user_id)
        if not state["connected"]:
            raise PhotoError("Student AI недоступен")
        source = "unlimited" if state["unlimited"] else "trial" if state["free_trial_available"] else "paid"
        amount = 5 if source == "paid" else 1
        identifier = secrets.token_urlsafe(24)
        with self.database.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM photo_quotes WHERE user_id=?", (user_id,)).fetchone()[0] >= 10:
                raise PhotoError("Слишком много запросов. Повторите через пять минут")
            db.execute("INSERT INTO photo_quotes(id,user_id,image_hash,source,amount,expires_at) VALUES(?,?,?,?,?,?)",
                       (identifier, user_id, hashlib.sha256(data).hexdigest(), source, amount, int(time.time()) + 300))
        return {"quote_id": identifier, "source": source, "credits": 5 if source == "paid" else 0,
                "uses_trial": source == "trial", "can_confirm": source != "paid" or state["balance"] >= 5,
                "retention_hours": 24}

    def latest(self, user_id):
        self.cleanup()
        with self.database.connection() as db:
            row = db.execute("SELECT * FROM photo_sessions WHERE user_id=? AND expires_at>? ORDER BY expires_at DESC LIMIT 1",
                             (user_id, int(time.time()))).fetchone()
        return {"session_id": row["id"], "tasks": json.loads(row["tasks"]), "expires_at": row["expires_at"]} if row else None

    def confirm(self, user_id, quote_id, data, mime):
        validate_photo(data, mime)
        with self.database.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            quote = db.execute("SELECT * FROM photo_quotes WHERE id=? AND user_id=?", (quote_id, user_id)).fetchone()
            if (not quote or quote["claimed"] or quote["expires_at"] <= time.time()
                    or quote["image_hash"] != hashlib.sha256(data).hexdigest()):
                raise PhotoError("Подтверждение истекло, использовано или относится к другому фото")
            db.execute("UPDATE photo_quotes SET claimed=1 WHERE id=?", (quote_id,))
        request_id = "photo:" + quote_id
        self.entitlements.reserve_credit(user_id, request_id, quote["amount"], expected_source=quote["source"])
        try:
            tasks, input_tokens, output_tokens = self.engine.recognize_photo(data, mime)
            if (not isinstance(tasks, list) or not 1 <= len(tasks) <= 30
                    or any(not isinstance(t, str) or not t.strip() or len(t) > 6000 for t in tasks)
                    or len(json.dumps(tasks, ensure_ascii=False)) > 24000):
                raise PhotoError("Не удалось распознать читаемые условия")
            expires = int(time.time()) + 24 * 3600
            # Commit setup usage and recognized session in the SAME short transaction.
            with self.database.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                changed = db.execute("""UPDATE ai_credit_reservations SET status='committed',
                    input_tokens=?,output_tokens=?,committed_at=?,updated_at=?
                    WHERE request_id=? AND user_id=? AND status='reserved'""",
                    (max(0, input_tokens), max(0, output_tokens), self.database._now(), self.database._now(), request_id, user_id))
                if changed.rowcount != 1:
                    raise ReservationConflict("Photo reservation is no longer pending")
                db.execute("INSERT INTO photo_sessions VALUES(?,?,?,?)", (quote_id, user_id, json.dumps(tasks, ensure_ascii=False), expires))
            return {"session_id": quote_id, "tasks": tasks, "expires_at": expires}
        except Exception:
            self.entitlements.release_reservation(request_id)
            raise

    def answer(self, user_id, session_id, selection, request_id):
        self.cleanup()
        if not self.entitlements.get_balance(user_id)["connected"]:
            raise PhotoError("Student AI временно недоступен")
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 128:
            raise PhotoError("Некорректный запрос")
        with self.database.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute("SELECT * FROM photo_sessions WHERE id=? AND user_id=? AND expires_at>?",
                                 (session_id, user_id, int(time.time()))).fetchone()
            if not session:
                raise PhotoError("Фото-сессия отсутствует или истекла")
            tasks = json.loads(session["tasks"])
            if (not isinstance(selection, list) or not selection or len(selection) > 30
                    or any(type(i) is not int or not 0 <= i < len(tasks) for i in selection)):
                raise PhotoError("Выберите задачи из распознанного списка")
            if db.execute("SELECT 1 FROM photo_requests WHERE id=?", (request_id,)).fetchone():
                raise PhotoError("Запрос уже принят; повторного запуска нет")
            # Bound free follow-ups while preserving the 24-hour photo setup semantics.
            if db.execute("SELECT COUNT(*) FROM photo_requests WHERE user_id=? AND created_at>?",
                          (user_id, int(time.time()) - 3600)).fetchone()[0] >= 20:
                raise PhotoError("Лимит: 20 фоторазборов в час. Попробуйте позже")
            db.execute("INSERT INTO photo_requests(id,session_id,user_id,status,created_at) VALUES(?,?,?,'started',?)",
                       (request_id, session_id, user_id, int(time.time())))
        try:
            assignment = "Реши выбранные задачи из фотографии. Неразборчивые части не выдумывай.\n\n" + "\n\n".join(
                f"Задача {i+1}: {tasks[i]}" for i in sorted(set(selection)))
            result = self.engine.analyze(assignment)
            input_tokens, output_tokens = result.usage()
            with self.database.connection() as db:
                db.execute("UPDATE photo_requests SET status='completed',input_tokens=?,output_tokens=? WHERE id=?",
                           (input_tokens, output_tokens, request_id))
            return result.to_dict()
        except Exception:
            with self.database.connection() as db:
                db.execute("UPDATE photo_requests SET status='failed' WHERE id=?", (request_id,))
            raise
