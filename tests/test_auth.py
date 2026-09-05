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


def test_production_security_headers_and_same_origin_browser_boundary(tmp_path: Path) -> None:
    production = create_app(Settings(
        tmp_path / "headers.db", "", "demo", environment="production",
        secure_cookies=True))
    with TestClient(production) as client:
        response = client.get("/")
        assert response.headers["strict-transport-security"] == "max-age=31536000"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["cross-origin-opener-policy"] == "same-origin-allow-popups"
        assert response.headers["cross-origin-resource-policy"] == "same-origin"
        policy = response.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in policy
        assert "connect-src 'self'" in policy
        assert "script-src 'self'" in policy
        assert "unsafe-inline" not in policy
        assert "access-control-allow-origin" not in response.headers
        assert client.get("/api/auth/session").headers["cache-control"] == "no-store"

    development = app_for(tmp_path / "dev-headers.db")
    with TestClient(development) as client:
        assert "strict-transport-security" not in client.get("/").headers


def test_dev_admin_is_explicit_and_impossible_in_production(tmp_path: Path) -> None:
    development = create_app(
        Settings(
            tmp_path / "dev-admin.db", "", "gpt-5.6-luna",
            environment="development", dev_login_enabled=True, dev_admin_enabled=True,
        )
    )
    with TestClient(development) as client:
        assert client.get("/admin").status_code == 200
        session = client.get("/api/auth/session").json()
        assert session["user"]["role"] == "admin"
        assert client.get("/api/admin/overview").status_code == 200

    disabled = create_app(
        Settings(
            tmp_path / "dev-disabled.db", "", "gpt-5.6-luna",
            environment="development", dev_login_enabled=True, dev_admin_enabled=False,
        )
    )
    with TestClient(disabled) as client:
        session = login(client)
        assert session["user"]["role"] == "user"
        assert client.get("/admin").status_code == 403

    production = create_app(
        Settings(
            tmp_path / "production-admin.db", "", "gpt-5.6-luna",
            environment="production", secure_cookies=False,
            dev_login_enabled=True, dev_admin_enabled=True,
        )
    )
    with TestClient(production) as client:
        assert client.post("/api/auth/dev-login").status_code == 404
        forged_admin = production.state.database.create_user("Not Telegram", role="admin")
        issued = production.state.sessions.issue(forged_admin["id"])
        client.cookies.set(SESSION_COOKIE, issued.token)
        assert client.get("/admin").status_code == 403
        assert client.get("/api/admin/overview").status_code == 403


def test_admin_page_rotates_stale_ordinary_development_session(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            tmp_path / "stale-dev-admin.db", "", "gpt-5.6-luna",
            environment="development", dev_login_enabled=True, dev_admin_enabled=True,
        )
    )
    with TestClient(app) as client:
        user = app.state.database.ensure_local_user()
        app.state.database.set_user_role(user["id"], "user")
        stale = app.state.sessions.issue(user["id"])
        client.cookies.set(
            SESSION_COOKIE, stale.token, domain="testserver.local", path="/"
        )

        response = client.get("/admin")

        assert response.status_code == 200
        assert client.cookies.get(
            SESSION_COOKIE, domain="testserver.local", path="/"
        ) != stale.token
        assert app.state.sessions.resolve(stale.token) is None
        assert client.get("/api/auth/session").json()["user"]["role"] == "admin"


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
