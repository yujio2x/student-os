from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schedule_import import MAX_UPLOAD_BYTES, ScheduleImportService, ScheduleImportError


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(Settings(tmp_path / "schedule.db", "", "gpt-5.6-luna"))
    with TestClient(app) as test_client:
        login = test_client.post("/api/auth/dev-login")
        test_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        yield test_client


def lesson_payload(**overrides) -> dict:
    payload = {
        "weekday": 5,
        "subject": "Архитектура ПО 🧩",
        "starts_at": "09:00",
        "ends_at": "10:20",
        "room": "D-101",
        "location": "Главный корпус",
        "teacher": "Ж. Өмірбек",
        "lesson_type": "Практика",
        "group_name": "SE-24",
        "notes": "Взять ноутбук",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("error,status", [
    (RuntimeError("private upstream failure"), 502),
    (ScheduleImportError("invalid schedule"), 422),
    (ScheduleImportError("missing OPENAI_API_KEY"), 503),
])
@pytest.mark.parametrize("all_tiles", [False, True])
def test_preview_failure_diagnostics_and_mapping(client, monkeypatch, caplog, error, status, all_tiles):
    from app import observability
    captured = []
    original_capture = observability.capture_import_exception
    def capture(category, exc, **kwargs):
        captured.append((category, exc))
        original_capture(category, exc, **kwargs)
    monkeypatch.setattr(observability, "capture_import_exception", capture)
    sentry = Mock()
    monkeypatch.setattr(observability, "_client", sentry)
    def fail(*args):
        raise error
    if all_tiles:
        importer = client.app.state.schedule_import
        importer.client = SimpleNamespace(responses=SimpleNamespace(create=Mock(side_effect=error)))
        tile = SimpleNamespace(mime="image/png", data=b"private image")
        monkeypatch.setattr(importer, "_prepare_image", lambda *args: SimpleNamespace(tiles=(tile, tile)))
    else:
        client.app.state.schedule_import.extract_with_warnings = fail
    before = client.get("/api/bootstrap").json()["lessons"]
    request_id = "12345678-1234-1234-1234-123456789abc"
    response = client.post("/api/schedule/import/preview", headers={"X-Request-ID": request_id},
                           files={"file": ("private.png", b"fixture", "image/png")})
    assert response.status_code == status
    assert client.get("/api/bootstrap").json()["lessons"] == before
    record = next(r for r in caplog.records if getattr(r, "pipeline_stage", None) == "preview_mapped")
    assert record.mapped_status == status and record.request_id == request_id
    assert captured == ([("schedule_import_preview_failed", error)] if status == 502 else [])
    assert sentry.capture_event.call_count == (1 if status == 502 else 0)
    if all_tiles:
        assert importer.client.responses.create.call_count == 2
        assert any(getattr(r, "pipeline_stage", None) == "all_tiles_failed" for r in caplog.records)
    if status == 502:
        event = sentry.capture_event.call_args.args[0]
        clean = observability.scrub({**event, "event_id": "a" * 32})
        assert clean["tags"]["request_id"] == request_id
        assert clean["tags"]["http_status"] == "502"
        assert clean["tags"]["pipeline_stage"] == "preview_mapped"
        assert clean["exception"]["values"][-1]["type"] == "RuntimeError"
    assert "private upstream" not in caplog.text and "OPENAI_API_KEY" not in caplog.text


def test_create_edit_delete_lesson_and_persist(client: TestClient) -> None:
    created = client.post("/api/lessons", json=lesson_payload())
    assert created.status_code == 201
    lesson_id = created.json()["id"]

    edited_payload = lesson_payload(
        weekday=6, starts_at="12:00", ends_at="13:30", location="онлайн",
        room="online 1", notes="Новая заметка"
    )
    edited = client.put(f"/api/lessons/{lesson_id}", json=edited_payload)

    assert edited.status_code == 200
    assert edited.json()["weekday"] == 6
    assert edited.json()["location"] == "онлайн"
    assert edited.json()["room"] == "online 1"
    assert edited.json()["notes"] == "Новая заметка"
    assert any(item["id"] == lesson_id for item in client.get("/api/bootstrap").json()["lessons"])

    deleted = client.delete(f"/api/lessons/{lesson_id}")
    assert deleted.status_code == 204
    assert all(item["id"] != lesson_id for item in client.get("/api/bootstrap").json()["lessons"])
    assert client.delete(f"/api/lessons/{lesson_id}").status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"starts_at": "10:20", "ends_at": "10:20"},
        {"starts_at": "18:00", "ends_at": "09:00"},
        {"starts_at": "25:00"},
        {"weekday": 7},
        {"subject": "   "},
    ],
)
def test_invalid_lesson_boundaries_are_rejected(client: TestClient, changes: dict) -> None:
    assert client.post("/api/lessons", json=lesson_payload(**changes)).status_code == 422


def test_overlapping_lesson_is_rejected(client: TestClient) -> None:
    first = client.post("/api/lessons", json=lesson_payload())
    overlap = client.post(
        "/api/lessons",
        json=lesson_payload(subject="Конфликт", starts_at="10:00", ends_at="11:00"),
    )

    assert first.status_code == 201
    assert overlap.status_code == 409
    assert "пересекается" in overlap.json()["detail"]


def test_import_preview_never_saves_and_confirm_is_explicit(client: TestClient) -> None:
    preview_rows = [lesson_payload(weekday=6, starts_at="15:00", ends_at="16:00")]
    client.app.state.schedule_import.extract_with_warnings = lambda *_: (preview_rows, [])
    before = len(client.get("/api/bootstrap").json()["lessons"])

    preview = client.post(
        "/api/schedule/import/preview",
        files={"file": ("synthetic.png", b"\x89PNG\r\n\x1a\nsynthetic", "image/png")},
    )

    assert preview.status_code == 200
    assert preview.json()["saved"] is False
    assert preview.json()["default_excluded_types"] == ["СРСП"]
    assert len(client.get("/api/bootstrap").json()["lessons"]) == before

    confirmed = client.post(
        "/api/schedule/import/confirm", json={"lessons": preview.json()["lessons"]}
    )
    assert confirmed.status_code == 201
    assert confirmed.json()["imported"] == 1
    assert len(client.get("/api/bootstrap").json()["lessons"]) == before + 1


def test_import_confirm_is_atomic_on_overlap(client: TestClient) -> None:
    before = len(client.get("/api/bootstrap").json()["lessons"])
    rows = [
        lesson_payload(weekday=6, starts_at="15:00", ends_at="16:00", subject="Первая"),
        lesson_payload(weekday=6, starts_at="15:30", ends_at="17:00", subject="Вторая"),
    ]

    response = client.post("/api/schedule/import/confirm", json={"lessons": rows})

    assert response.status_code == 409
    assert len(client.get("/api/bootstrap").json()["lessons"]) == before


def test_malformed_and_oversized_uploads_are_rejected(client: TestClient) -> None:
    malformed = client.post(
        "/api/schedule/import/preview",
        files={"file": ("broken.png", b"not-a-png", "image/png")},
    )
    oversized = client.post(
        "/api/schedule/import/preview",
        files={"file": ("large.jpg", b"\xff\xd8\xff" + b"0" * MAX_UPLOAD_BYTES, "image/jpeg")},
    )

    assert malformed.status_code == 422
    assert oversized.status_code == 413


def test_digital_pdf_fallback_parser_handles_unicode() -> None:
    rows = ScheduleImportService.parse_schedule_text(
        "Понедельник | 08:30-09:50 | Қазақ тілі | A-12 | А. Қасым | Практика"
    )

    assert rows == [{
        "weekday": 0,
        "subject": "Қазақ тілі",
        "starts_at": "08:30",
        "ends_at": "09:50",
        "room": "A-12",
        "location": "",
        "teacher": "А. Қасым",
        "lesson_type": "Практика",
        "group_name": "",
        "notes": "",
    }]
