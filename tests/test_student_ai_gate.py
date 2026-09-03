from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class SpyStudy:
    client = object()

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def analyze(self, assignment: str, subject: str = "", title: str = ""):
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic failure")

        class Result:
            @staticmethod
            def to_dict() -> dict:
                return {
                    "subject": "Алгоритмы", "assignment_title": "Разбор",
                    "analysis": "Понимание", "explanation": "Решение",
                    "approach": ["Шаг"], "checks": ["Проверка"],
                    "how_to_defend": "Объяснение для защиты",
                    "defense_questions": ["Почему?"], "pitfalls": ["Слепое копирование"],
                    "suggested_due_at": None, "mode": "demo",
                }

        return Result()


def logged_in_app(path: Path, source: str = "unconnected"):
    app = create_app(
        Settings(path, "", "gpt-5.6-luna", entitlement_source=source)
    )
    client = TestClient(app)
    client.__enter__()
    session = client.post("/api/auth/dev-login").json()
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    return app, client, session["user"]["id"]


def payload(request_id: str = "student-ai-request") -> dict:
    return {"assignment": "Реши задачу", "request_id": request_id}


def test_unlinked_user_never_calls_ai_or_touches_credits(tmp_path: Path) -> None:
    app, client, user_id = logged_in_app(tmp_path / "unlinked.db")
    spy = SpyStudy()
    app.state.study = spy
    try:
        response = client.post("/api/study/analyze", json=payload())
        assert response.status_code == 403
        assert "Telegram" in response.json()["detail"]
        assert spy.calls == 0
        with app.state.database.connection() as db:
            assert db.execute(
                "SELECT COUNT(*) FROM ai_entitlements WHERE user_id=?", (user_id,)
            ).fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM ai_credit_reservations").fetchone()[0] == 0
    finally:
        client.__exit__(None, None, None)


def test_linked_user_reaches_honest_unconnected_entitlement_gate(tmp_path: Path) -> None:
    app, client, user_id = logged_in_app(tmp_path / "linked-unconnected.db")
    spy = SpyStudy()
    app.state.study = spy
    app.state.database.link_telegram_identity(user_id, "777", "linked", "Linked User")
    try:
        response = client.post("/api/study/analyze", json=payload())
        assert response.status_code == 409
        assert "не подключён" in response.json()["detail"]
        assert spy.calls == 0
        with app.state.database.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM ai_credit_reservations").fetchone()[0] == 0
    finally:
        client.__exit__(None, None, None)


def test_linked_connected_user_reserves_commits_and_blocks_duplicate(tmp_path: Path) -> None:
    app, client, user_id = logged_in_app(tmp_path / "connected.db", source="local")
    spy = SpyStudy()
    app.state.study = spy
    app.state.database.link_telegram_identity(user_id, "778", "ready", "Ready User")
    app.state.entitlements.get_balance(user_id)
    with app.state.database.connection() as db:
        db.execute("UPDATE ai_entitlements SET balance=1 WHERE user_id=?", (user_id,))
    try:
        response = client.post("/api/study/analyze", json=payload("same-request"))
        duplicate = client.post("/api/study/analyze", json=payload("same-request"))
        assert response.status_code == 200
        assert duplicate.status_code == 409
        assert spy.calls == 1
        assert app.state.entitlements.get_balance(user_id)["balance"] == 0
        with app.state.database.connection() as db:
            assert db.execute(
                "SELECT status FROM ai_credit_reservations WHERE request_id='same-request'"
            ).fetchone()[0] == "committed"
    finally:
        client.__exit__(None, None, None)


def test_ai_failure_releases_reserved_credit(tmp_path: Path) -> None:
    app, client, user_id = logged_in_app(tmp_path / "failure.db", source="local")
    app.state.study = SpyStudy(fail=True)
    app.state.database.link_telegram_identity(user_id, "779", "failure", "Failure User")
    app.state.entitlements.get_balance(user_id)
    with app.state.database.connection() as db:
        db.execute("UPDATE ai_entitlements SET balance=1 WHERE user_id=?", (user_id,))
    try:
        assert client.post("/api/study/analyze", json=payload("failed-request")).status_code == 502
        assert app.state.entitlements.get_balance(user_id)["balance"] == 1
    finally:
        client.__exit__(None, None, None)
