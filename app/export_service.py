from __future__ import annotations

import json
from datetime import UTC, datetime

from app.database import Database


class ExportTooLargeError(ValueError):
    pass


class OwnedDataExportService:
    """Build a bounded, versioned export containing only user-owned product data."""

    schema_version = 1

    def __init__(
        self, database: Database, max_records: int = 10_000, max_bytes: int = 5 * 1024 * 1024
    ) -> None:
        self.database = database
        self.max_records = max_records
        self.max_bytes = max_bytes

    @staticmethod
    def _owned(records: list[dict]) -> list[dict]:
        return [
            {key: value for key, value in record.items() if key != "user_id"}
            for record in records
        ]

    def render(self, user_id: str) -> bytes:
        lessons = self.database.lessons(user_id)
        deadlines = self.database.deadlines(user_id)
        if len(lessons) + len(deadlines) > self.max_records:
            raise ExportTooLargeError("Слишком много записей для одного экспорта")

        preferences = {
            key: value
            for key, value in self.database.preferences(user_id).items()
            if key != "user_id"
        }
        document = {
            "schema_version": self.schema_version,
            "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "preferences": preferences,
            "lessons": self._owned(lessons),
            "deadlines": self._owned(deadlines),
        }
        rendered = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
        if len(rendered) > self.max_bytes:
            raise ExportTooLargeError("Экспорт превышает безопасный лимит 5 МБ")
        return rendered
