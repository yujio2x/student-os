from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class LessonConflictError(ValueError):
    pass


class DeadlineConflictError(ValueError):
    pass


class Database:
    """Small local-first store. All user-owned rows carry a user_id for future auth."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def initialize(self) -> None:
        with self.connection() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6),
                    subject TEXT NOT NULL CHECK(length(subject) BETWEEN 1 AND 120),
                    starts_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    room TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    teacher TEXT NOT NULL DEFAULT '',
                    lesson_type TEXT NOT NULL DEFAULT '',
                    group_name TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    CHECK(starts_at < ends_at)
                );

                CREATE TABLE IF NOT EXISTS deadlines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 160),
                    subject TEXT NOT NULL DEFAULT '',
                    due_at TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'manual',
                    completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS preferences (
                    user_id TEXT PRIMARY KEY,
                    theme TEXT NOT NULL DEFAULT 'light' CHECK(theme IN ('light', 'dark')),
                    schedule_view TEXT NOT NULL DEFAULT 'week' CHECK(schedule_view IN ('week', 'day')),
                    mobile_schedule_view TEXT NOT NULL DEFAULT 'day'
                        CHECK(mobile_schedule_view IN ('week', 'day')),
                    visible_fields TEXT NOT NULL DEFAULT 'room,teacher,lesson_type'
                );

                CREATE INDEX IF NOT EXISTS idx_lessons_user_day
                    ON lessons(user_id, weekday, starts_at);
                CREATE INDEX IF NOT EXISTS idx_deadlines_user_due
                    ON deadlines(user_id, due_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_deadlines_deduplicate
                    ON deadlines(user_id, title, due_at, source);
                """
            )
            columns = {
                str(row["name"]) for row in db.execute("PRAGMA table_info(preferences)").fetchall()
            }
            if "mobile_schedule_view" not in columns:
                db.execute(
                    "ALTER TABLE preferences ADD COLUMN mobile_schedule_view TEXT NOT NULL DEFAULT 'day'"
                )
            lesson_columns = {
                str(row["name"]) for row in db.execute("PRAGMA table_info(lessons)").fetchall()
            }
            if "location" not in lesson_columns:
                db.execute(
                    "ALTER TABLE lessons ADD COLUMN location TEXT NOT NULL DEFAULT ''"
                )

    def seed_demo(self, user_id: str) -> None:
        with self.connection() as db:
            existing = db.execute(
                "SELECT 1 FROM lessons WHERE user_id=? LIMIT 1", (user_id,)
            ).fetchone()
            if existing:
                return
            lessons = [
                (0, "Алгоритмы", "09:00", "10:20", "B-204", "", "А. Иманов", "Лекция"),
                (0, "Английский язык", "11:00", "12:20", "A-113", "", "Д. Ким", "Практика"),
                (1, "Базы данных", "10:00", "11:20", "C-310", "", "М. Садыкова", "Лабораторная"),
                (2, "Математика", "09:30", "10:50", "B-118", "", "Р. Алиев", "Практика"),
                (3, "Алгоритмы", "13:00", "14:20", "B-204", "", "А. Иманов", "Практика"),
                (4, "Проектирование", "11:00", "12:20", "D-402", "", "Е. Пак", "Лекция"),
            ]
            db.executemany(
                """INSERT INTO lessons
                (user_id, weekday, subject, starts_at, ends_at, room, location, teacher, lesson_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(user_id, *lesson) for lesson in lessons],
            )
            db.execute("INSERT OR IGNORE INTO preferences(user_id) VALUES (?)", (user_id,))

    def lessons(self, user_id: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM lessons WHERE user_id=? ORDER BY weekday, starts_at", (user_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _lesson_conflict(
        db: sqlite3.Connection, user_id: str, weekday: int, starts_at: str,
        ends_at: str, exclude_id: int | None = None,
    ) -> sqlite3.Row | None:
        query = (
            "SELECT * FROM lessons WHERE user_id=? AND weekday=? "
            "AND starts_at < ? AND ends_at > ?"
        )
        params: list[object] = [user_id, weekday, ends_at, starts_at]
        if exclude_id is not None:
            query += " AND id<>?"
            params.append(exclude_id)
        query += " ORDER BY starts_at LIMIT 1"
        return db.execute(query, params).fetchone()

    def add_lesson(self, user_id: str, lesson: dict) -> dict:
        with self.connection() as db:
            conflict = self._lesson_conflict(
                db, user_id, lesson["weekday"], lesson["starts_at"], lesson["ends_at"]
            )
            if conflict:
                raise LessonConflictError(
                    f"Время пересекается с занятием «{conflict['subject']}» "
                    f"({conflict['starts_at']}–{conflict['ends_at']})"
                )
            cursor = db.execute(
                """INSERT INTO lessons
                (user_id, weekday, subject, starts_at, ends_at, room, location, teacher,
                 lesson_type, group_name, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id, lesson["weekday"], lesson["subject"], lesson["starts_at"],
                    lesson["ends_at"], lesson["room"], lesson["location"], lesson["teacher"],
                    lesson["lesson_type"], lesson["group_name"], lesson["notes"],
                ),
            )
            row = db.execute("SELECT * FROM lessons WHERE id=?", (cursor.lastrowid,)).fetchone()
        return dict(row)

    def update_lesson(self, user_id: str, lesson_id: int, lesson: dict) -> dict | None:
        with self.connection() as db:
            owned = db.execute(
                "SELECT 1 FROM lessons WHERE id=? AND user_id=?", (lesson_id, user_id)
            ).fetchone()
            if owned is None:
                return None
            conflict = self._lesson_conflict(
                db, user_id, lesson["weekday"], lesson["starts_at"],
                lesson["ends_at"], exclude_id=lesson_id,
            )
            if conflict:
                raise LessonConflictError(
                    f"Время пересекается с занятием «{conflict['subject']}» "
                    f"({conflict['starts_at']}–{conflict['ends_at']})"
                )
            db.execute(
                """UPDATE lessons SET weekday=?, subject=?, starts_at=?, ends_at=?, room=?,
                location=?, teacher=?, lesson_type=?, group_name=?, notes=?
                WHERE id=? AND user_id=?""",
                (
                    lesson["weekday"], lesson["subject"], lesson["starts_at"],
                    lesson["ends_at"], lesson["room"], lesson["location"], lesson["teacher"],
                    lesson["lesson_type"], lesson["group_name"], lesson["notes"],
                    lesson_id, user_id,
                ),
            )
            row = db.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        return dict(row)

    def delete_lesson(self, user_id: str, lesson_id: int) -> bool:
        with self.connection() as db:
            cursor = db.execute(
                "DELETE FROM lessons WHERE id=? AND user_id=?", (lesson_id, user_id)
            )
            return cursor.rowcount == 1

    def import_lessons(self, user_id: str, lessons: list[dict]) -> list[dict]:
        """Import a reviewed preview atomically; never accepts partial persistence."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for index, lesson in enumerate(lessons):
                for previous in lessons[:index]:
                    if (
                        previous["weekday"] == lesson["weekday"]
                        and previous["starts_at"] < lesson["ends_at"]
                        and previous["ends_at"] > lesson["starts_at"]
                    ):
                        raise LessonConflictError(
                            f"Строки импорта «{previous['subject']}» и «{lesson['subject']}» "
                            "пересекаются по времени"
                        )
                conflict = self._lesson_conflict(
                    db, user_id, lesson["weekday"], lesson["starts_at"], lesson["ends_at"]
                )
                if conflict:
                    raise LessonConflictError(
                        f"«{lesson['subject']}» пересекается с существующим занятием "
                        f"«{conflict['subject']}»"
                    )

            inserted_ids: list[int] = []
            for lesson in lessons:
                cursor = db.execute(
                    """INSERT INTO lessons
                    (user_id, weekday, subject, starts_at, ends_at, room, location, teacher,
                     lesson_type, group_name, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id, lesson["weekday"], lesson["subject"], lesson["starts_at"],
                        lesson["ends_at"], lesson["room"], lesson["location"], lesson["teacher"],
                        lesson["lesson_type"], lesson["group_name"], lesson["notes"],
                    ),
                )
                inserted_ids.append(int(cursor.lastrowid))
            placeholders = ",".join("?" for _ in inserted_ids)
            rows = db.execute(
                f"SELECT * FROM lessons WHERE id IN ({placeholders}) ORDER BY weekday, starts_at",
                inserted_ids,
            ).fetchall()
        return [dict(row) for row in rows]

    def deadlines(self, user_id: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM deadlines WHERE user_id=? ORDER BY due_at", (user_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def preferences(self, user_id: str) -> dict:
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO preferences(user_id) VALUES (?)", (user_id,))
            row = db.execute("SELECT * FROM preferences WHERE user_id=?", (user_id,)).fetchone()
        result = dict(row)
        result["visible_fields"] = [item for item in result["visible_fields"].split(",") if item]
        return result

    def update_preferences(
        self, user_id: str, theme: str, schedule_view: str,
        mobile_schedule_view: str, visible_fields: list[str],
    ) -> dict:
        with self.connection() as db:
            db.execute(
                """INSERT INTO preferences
                (user_id, theme, schedule_view, mobile_schedule_view, visible_fields)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET theme=excluded.theme,
                schedule_view=excluded.schedule_view,
                mobile_schedule_view=excluded.mobile_schedule_view,
                visible_fields=excluded.visible_fields""",
                (user_id, theme, schedule_view, mobile_schedule_view, ",".join(visible_fields)),
            )
        return self.preferences(user_id)

    def add_deadline(
        self, user_id: str, title: str, subject: str, due_at: str,
        description: str, source: str,
    ) -> dict:
        with self.connection() as db:
            db.execute(
                """INSERT OR IGNORE INTO deadlines
                (user_id, title, subject, due_at, description, source)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, title, subject, due_at, description, source),
            )
            row = db.execute(
                """SELECT * FROM deadlines
                WHERE user_id=? AND title=? AND due_at=? AND source=?""",
                (user_id, title, due_at, source),
            ).fetchone()
        return dict(row)

    def set_deadline_completed(self, user_id: str, deadline_id: int, completed: bool) -> dict | None:
        with self.connection() as db:
            cursor = db.execute(
                "UPDATE deadlines SET completed=? WHERE id=? AND user_id=?",
                (int(completed), deadline_id, user_id),
            )
            if cursor.rowcount != 1:
                return None
            row = db.execute("SELECT * FROM deadlines WHERE id=?", (deadline_id,)).fetchone()
        return dict(row)

    def update_deadline(
        self, user_id: str, deadline_id: int, title: str, subject: str, due_at: str,
        description: str, completed: bool,
    ) -> dict | None:
        with self.connection() as db:
            try:
                cursor = db.execute(
                    """UPDATE deadlines SET title=?, subject=?, due_at=?, description=?, completed=?
                    WHERE id=? AND user_id=?""",
                    (title, subject, due_at, description, int(completed), deadline_id, user_id),
                )
            except sqlite3.IntegrityError as exc:
                raise DeadlineConflictError("Такой дедлайн уже существует") from exc
            if cursor.rowcount != 1:
                return None
            row = db.execute(
                "SELECT * FROM deadlines WHERE id=? AND user_id=?", (deadline_id, user_id)
            ).fetchone()
        return dict(row)

    def delete_deadline(self, user_id: str, deadline_id: int) -> bool:
        with self.connection() as db:
            cursor = db.execute(
                "DELETE FROM deadlines WHERE id=? AND user_id=?", (deadline_id, user_id)
            )
            return cursor.rowcount == 1
