from __future__ import annotations

import sqlite3
from pathlib import Path

from app.database import Database
from app.schedule_import import ScheduleImportService


FIXTURE = Path(__file__).parent / "fixtures" / "platonus_extract.txt"


def parsed_rows() -> list[dict]:
    return ScheduleImportService.parse_schedule_text(FIXTURE.read_text(encoding="utf-8"))


def test_platonus_multiline_fields_are_separated() -> None:
    rows = parsed_rows()
    first = rows[0]

    assert first["subject"] == "Алгоритмизация и программирование"
    assert first["lesson_type"] == "Л"
    assert first["teacher"] == "сениор-лектор Балғабек А. А."
    assert first["location"] == "Байзак центр"
    assert first["room"] == "613 Б"
    assert "Балғабек" not in first["subject"]


def test_academic_title_unknown_type_and_unicode_degrade_safely() -> None:
    row = next(item for item in parsed_rows() if item["subject"] == "Дискретная математика")

    assert row["lesson_type"] == "ПР-2"
    assert row["teacher"] == "ассистент-профессор, к.ф.-м.н. Таласбаева Ж. Т."
    assert row["location"] == "Главный"
    assert row["room"] == "401"


def test_online_room_and_non_person_teacher_are_not_subject() -> None:
    row = next(item for item in parsed_rows() if item["lesson_type"] == "СРСП")

    assert row["subject"] == "Иностранный язык"
    assert row["teacher"] == "МООК 1 К."
    assert row["location"] == "онлайн"
    assert row["room"] == "online 1"


def test_empty_slots_are_ignored_and_consecutive_lessons_stay_separate() -> None:
    rows = parsed_rows()
    algorithm_rows = [item for item in rows if item["subject"] == "Алгоритмизация и программирование"]

    assert len(rows) == 6
    assert [item["starts_at"] for item in algorithm_rows] == ["08:00", "09:00"]
    assert not any(item["starts_at"] == "10:00" for item in rows)


def test_vacancy_teacher_stays_out_of_subject() -> None:
    row = next(item for item in parsed_rows() if item["lesson_type"] == "СПЗ")

    assert row["subject"] == "Иностранный язык"
    assert row["teacher"] == "Вакансия 23 М."
    assert row["location"] == "Байзак центр"
    assert row["room"] == "328 Б"


def test_existing_lessons_database_gets_location_migration(tmp_path: Path) -> None:
    path = tmp_path / "old-lessons.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            weekday INTEGER NOT NULL,
            subject TEXT NOT NULL,
            starts_at TEXT NOT NULL,
            ends_at TEXT NOT NULL,
            room TEXT NOT NULL DEFAULT '',
            teacher TEXT NOT NULL DEFAULT '',
            lesson_type TEXT NOT NULL DEFAULT '',
            group_name TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '')"""
        )

    database = Database(path)
    database.initialize()

    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(lessons)")}
    assert "location" in columns
