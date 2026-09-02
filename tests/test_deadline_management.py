from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Database
from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(Settings(tmp_path / "deadlines.db", "", "gpt-5.6-luna"))
    with TestClient(app) as test_client:
        yield test_client


def payload(**changes) -> dict:
    result = {
        "title": "Зачёт по қазақ тілі 🚀",
        "subject": "Қазақ тілі",
        "due_at": "2025-01-02T09:15:00",
        "description": "Подготовить конспект",
        "source": "manual",
    }
    result.update(changes)
    return result


def test_manual_deadline_full_lifecycle_allows_past_and_unicode(client: TestClient) -> None:
    created = client.post("/api/deadlines", json=payload())
    assert created.status_code == 201

    deadline_id = created.json()["id"]
    updated = client.put(
        f"/api/deadlines/{deadline_id}",
        json={**payload(title="Исправленный дедлайн", source="ai-study"), "completed": True},
    )
    assert updated.status_code == 200
    assert updated.json()["completed"] == 1
    assert updated.json()["source"] == "manual"
    assert client.delete(f"/api/deadlines/{deadline_id}").status_code == 204
    assert client.delete(f"/api/deadlines/{deadline_id}").status_code == 404


def test_ai_deadline_uses_same_edit_flow(client: TestClient) -> None:
    created = client.post("/api/deadlines", json=payload(source="ai-study")).json()
    updated = client.put(
        f"/api/deadlines/{created['id']}",
        json={**payload(title="Отредактировано вручную"), "completed": False},
    )
    assert updated.status_code == 200
    assert updated.json()["source"] == "ai-study"
    assert updated.json()["title"] == "Отредактировано вручную"


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "   "},
        {"title": "x" * 161},
        {"subject": "x" * 121},
        {"description": "x" * 4001},
    ],
)
def test_deadline_boundaries_are_rejected(client: TestClient, changes: dict) -> None:
    assert client.post("/api/deadlines", json=payload(**changes)).status_code == 422


def test_date_without_time_uses_existing_midnight_semantics(client: TestClient) -> None:
    response = client.post("/api/deadlines", json=payload(due_at="2026-09-02"))
    assert response.status_code == 201
    assert response.json()["due_at"] == "2026-09-02T00:00"


def test_duplicate_submit_is_idempotent(client: TestClient) -> None:
    first = client.post("/api/deadlines", json=payload()).json()
    second = client.post("/api/deadlines", json=payload()).json()
    assert first["id"] == second["id"]
    assert len(client.get("/api/bootstrap").json()["deadlines"]) == 1


def test_missing_and_foreign_deadlines_cannot_be_changed(tmp_path: Path) -> None:
    database = Database(tmp_path / "ownership.db")
    database.initialize()
    owned = database.add_deadline(
        "owner", "Private", "", "2026-09-02T18:00", "", "manual"
    )
    assert database.update_deadline(
        "other", owned["id"], "Stolen", "", "2026-09-02T18:00", "", False
    ) is None
    assert database.delete_deadline("other", owned["id"]) is False
    assert database.deadlines("owner")[0]["title"] == "Private"
