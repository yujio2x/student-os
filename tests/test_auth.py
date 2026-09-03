from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE
from app.config import Settings
from app.database import Database
from app.main import create_app


def app_for(path: Path, environment: str = "development"):
    return create_app(
        Settings(path, "", "gpt-5.6-luna", environment=environment, secure_cookies=False)
    )


def login(client: TestClient) -> dict:
    response = client.post("/api/auth/dev-login")
    assert response.status_code == 200
    session = response.json()
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    return session


def lesson_payload() -> dict:
    return {
        "weekday": 6,
        "subject": "Session isolation",
        "starts_at": "18:00",
        "ends_at": "19:00",
        "room": "",
        "location": "",
        "teacher": "",
        "lesson_type": "",
        "group_name": "",
        "notes": "",
    }


def test_missing_invalid_and_expired_sessions_are_rejected(tmp_path: Path) -> None:
    app = app_for(tmp_path / "auth.db")
    with TestClient(app) as client:
        assert client.get("/api/bootstrap").status_code == 401
        client.cookies.set(SESSION_COOKIE, "forged")
        assert client.get("/api/bootstrap").status_code == 401

        user = app.state.database.ensure_local_user()
        raw = "expired-token"
        expired = (datetime.now(UTC) - timedelta(seconds=1)).isoformat(timespec="seconds")
        app.state.database.create_session(
            app.state.sessions.token_hash(raw), user["id"], "expired-csrf", expired
        )
        client.cookies.set(SESSION_COOKIE, raw)
        assert client.get("/api/bootstrap").status_code == 401


def test_login_rotates_session_and_logout_prevents_reuse(tmp_path: Path) -> None:
    app = app_for(tmp_path / "logout.db")
    with TestClient(app) as client:
        client.cookies.set(
            SESSION_COOKIE, "attacker-chosen", domain="testserver.local", path="/"
        )
        session = login(client)
        issued_cookie = client.cookies.get(SESSION_COOKIE)
        assert issued_cookie and issued_cookie != "attacker-chosen"

        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/bootstrap").status_code == 401
        client.cookies.set(
            SESSION_COOKIE, issued_cookie, domain="testserver.local", path="/"
        )
        assert client.get("/api/bootstrap").status_code == 401
        assert session["user"]["id"] != "local-demo-user"


def test_mutations_require_csrf_and_production_has_no_dev_login(tmp_path: Path) -> None:
    app = app_for(tmp_path / "csrf.db")
    with TestClient(app) as client:
        login(client)
        del client.headers["X-CSRF-Token"]
        assert client.post("/api/lessons", json=lesson_payload()).status_code == 403
        client.headers["X-CSRF-Token"] = "modified"
        assert client.post("/api/lessons", json=lesson_payload()).status_code == 403

    production = app_for(tmp_path / "production.db", environment="production")
    with TestClient(production) as client:
        assert client.post("/api/auth/dev-login").status_code == 404
        assert client.get("/api/bootstrap").status_code == 401


def test_users_cannot_read_or_modify_foreign_objects(tmp_path: Path) -> None:
    app = app_for(tmp_path / "isolation.db")
    with TestClient(app) as client:
        owner = login(client)
        created_lesson = client.post("/api/lessons", json=lesson_payload()).json()
        created_deadline = client.post(
            "/api/deadlines",
            json={"title": "Private", "due_at": "2026-10-01T12:00", "source": "manual"},
        ).json()

        other = app.state.database.create_user("Other student")
        issued = app.state.sessions.issue(other["id"])
        client.cookies.set(SESSION_COOKIE, issued.token)
        client.headers["X-CSRF-Token"] = issued.csrf_token

        bootstrap = client.get("/api/bootstrap").json()
        assert bootstrap["lessons"] == []
        assert bootstrap["deadlines"] == []
        assert client.put(
            f"/api/lessons/{created_lesson['id']}", json=lesson_payload()
        ).status_code == 404
        assert client.delete(f"/api/deadlines/{created_deadline['id']}").status_code == 404
        assert app.state.database.lessons(owner["user"]["id"])[-1]["subject"] == "Session isolation"


def test_browser_supplied_user_id_never_selects_owner(tmp_path: Path) -> None:
    app = app_for(tmp_path / "identity.db")
    with TestClient(app) as client:
        session = login(client)
        other = app.state.database.create_user("Target")
        response = client.post(
            "/api/lessons", json={**lesson_payload(), "user_id": other["id"]}
        )
        assert response.status_code == 201
        assert app.state.database.lessons(other["id"]) == []
        assert any(
            row["id"] == response.json()["id"]
            for row in app.state.database.lessons(session["user"]["id"])
        )


def test_legacy_local_rows_migrate_once_to_stable_internal_user(tmp_path: Path) -> None:
    database = Database(tmp_path / "legacy.db")
    database.initialize()
    database.seed_demo("local-demo-user")

    first = database.ensure_local_user()
    second = database.ensure_local_user()

    assert first["id"] == second["id"]
    assert first["id"] != "local-demo-user"
    assert len(database.lessons(first["id"])) == 6
    assert database.lessons("local-demo-user") == []
