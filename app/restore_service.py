"""Owned-data replacement: validate, preview, revalidate snapshot, atomic confirm."""
import hashlib
import json
import secrets
import time

from pydantic import ValidationError

MAX_RESTORE_BYTES = 5 * 1024 * 1024


class RestoreError(ValueError):
    pass


class RestoreConflict(RestoreError):
    pass


class RestoreService:
    def __init__(self, database, lesson_model, deadline_model, preferences_model):
        self.database = database
        self.models = lesson_model, deadline_model, preferences_model

    def initialize(self):
        if getattr(self.database, "is_postgres", False):
            return
        with self.database.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS restore_previews (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, file_hash TEXT NOT NULL,
                state_hash TEXT NOT NULL, expires_at INTEGER NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)""")

    @staticmethod
    def digest(data):
        return hashlib.sha256(data).hexdigest()

    def validate(self, raw):
        if not raw or len(raw) > MAX_RESTORE_BYTES:
            raise RestoreError("Архив должен быть не больше 5 МБ")
        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise RestoreError("Повторяющийся ключ JSON")
                result[key] = value
            return result
        try:
            data = json.loads(raw, object_pairs_hook=unique_keys)
            if not isinstance(data, dict) or set(data) != {"schema_version", "exported_at", "preferences", "lessons", "deadlines"}:
                raise RestoreError("Неизвестная структура архива")
            if type(data["schema_version"]) is not int or data["schema_version"] != 1:
                raise RestoreError("Версия архива не поддерживается")
            if not isinstance(data["lessons"], list) or not isinstance(data["deadlines"], list) or len(data["lessons"]) + len(data["deadlines"]) > 10000:
                raise RestoreError("Слишком много записей")
            lesson_model, deadline_model, preferences_model = self.models
            def record(value, model, metadata):
                if not isinstance(value, dict) or set(value) - set(model.model_fields) - metadata:
                    raise RestoreError("Архив содержит неизвестные или приватные поля")
                return model.model_validate({k: v for k, v in value.items() if k in model.model_fields})
            preferences = record(data["preferences"], preferences_model, set()).model_dump()
            lessons = [record(x, lesson_model, {"id"}).record() for x in data["lessons"]]
            deadlines = []
            seen = set()
            for item in data["deadlines"]:
                parsed = record(item, deadline_model, {"id", "completed", "created_at"})
                if type(item.get("completed")) not in (bool, int) or item["completed"] not in (0, 1):
                    raise RestoreError("Некорректный статус дедлайна")
                value = parsed.model_dump(mode="json")
                value["completed"] = int(item["completed"])
                key = value["title"], value["due_at"], value["source"]
                if key in seen:
                    raise RestoreError("Повторяющийся дедлайн")
                seen.add(key)
                deadlines.append(value)
            ordered = sorted(lessons, key=lambda x: (x["weekday"], x["starts_at"]))
            for left, right in zip(ordered, ordered[1:]):
                if left["weekday"] == right["weekday"] and left["ends_at"] > right["starts_at"]:
                    raise RestoreError("Занятия в архиве пересекаются по времени")
            return {"preferences": preferences, "lessons": lessons, "deadlines": deadlines}
        except (ValueError, TypeError, KeyError, RecursionError, UnicodeError, ValidationError) as exc:
            if isinstance(exc, RestoreError):
                raise
            raise RestoreError("Архив повреждён или содержит некорректные поля") from None

    def snapshot(self, db, user_id):
        content = {}
        for table in ("lessons", "deadlines", "preferences"):
            order = "user_id" if table == "preferences" else "id"
            content[table] = [dict(row) for row in db.execute(f"SELECT * FROM {table} WHERE user_id=? ORDER BY {order}", (user_id,))]
        encoded = json.dumps(content, sort_keys=True, ensure_ascii=False).encode()
        if len(encoded) > MAX_RESTORE_BYTES:
            raise RestoreError("Текущие данные превышают лимит безопасного восстановления")
        return self.digest(encoded), {key: len(value) for key, value in content.items()}

    def preview(self, user_id, raw):
        data = self.validate(raw)
        identifier = secrets.token_urlsafe(24)
        with self.database.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM restore_previews WHERE expires_at<=?", (int(time.time()),))
            db.execute("DELETE FROM restore_previews WHERE user_id=?", (user_id,))
            state_hash, counts = self.snapshot(db, user_id)
            db.execute("INSERT INTO restore_previews(id,user_id,file_hash,state_hash,expires_at) VALUES(?,?,?,?,?)",
                       (identifier, user_id, self.digest(raw), state_hash, int(time.time()) + 300))
        return {"preview_id": identifier, "current": counts,
                "replacement": {"lessons": len(data["lessons"]), "deadlines": len(data["deadlines"]), "preferences": 1},
                "mode": "replace", "expires_in_seconds": 300}

    def confirm(self, user_id, raw, preview_id):
        data = self.validate(raw)
        with self.database.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            preview = db.execute("SELECT * FROM restore_previews WHERE id=? AND user_id=?", (preview_id, user_id)).fetchone()
            if not preview or preview["consumed"] or preview["expires_at"] <= time.time() or preview["file_hash"] != self.digest(raw):
                raise RestoreConflict("Предпросмотр истёк или уже использован. Загрузите архив снова")
            current_hash, _ = self.snapshot(db, user_id)
            if current_hash != preview["state_hash"]:
                raise RestoreConflict("Данные изменились после предпросмотра. Проверьте архив снова")
            for table in ("lessons", "deadlines", "preferences"):
                db.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
            for table in ("lessons", "deadlines"):
                for item in data[table]:
                    # Keys come only from validated server models, never arbitrary JSON.
                    fields = list(item)
                    db.execute(f"INSERT INTO {table}(user_id,{','.join(fields)}) VALUES({','.join('?' for _ in range(len(fields)+1))})",
                               (user_id, *item.values()))
            preferences = data["preferences"]
            db.execute("INSERT INTO preferences VALUES(?,?,?,?,?)", (user_id, preferences["theme"], preferences["schedule_view"],
                       preferences["mobile_schedule_view"], ",".join(preferences["visible_fields"])))
            db.execute("UPDATE restore_previews SET consumed=1 WHERE id=?", (preview_id,))
        return {"restored": True, "lessons": len(data["lessons"]), "deadlines": len(data["deadlines"])}
