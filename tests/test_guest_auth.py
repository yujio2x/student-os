from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE
from app.config import Settings
from app.main import create_app


def app_for(path: Path):
    return create_app(Settings(
        path, "", "demo", environment="production", secure_cookies=False,
        telegram_client_id="1234", telegram_client_secret="fixture-secret",
        telegram_redirect_uri="https://example.test/api/auth/telegram/callback",
        owner_telegram_id="8247777174",
    ))


def guest(client: TestClient) -> dict:
    session = client.post("/api/auth/guest").json()
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    return session


def lesson(subject: str = "Гостевая математика") -> dict:
    return {
        "weekday": 1, "subject": subject, "starts_at": "09:00", "ends_at": "10:00",
        "room": "", "location": "", "teacher": "", "lesson_type": "",
        "group_name": "", "notes": "",
    }


def deadline(title: str = "Гостевой дедлайн") -> dict:
    return {"title": title, "due_at": "2026-10-10T12:00", "source": "manual"}


def add_deadline(database, user_id: str, title: str) -> dict:
    return database.add_deadline(
        user_id, title, "", "2026-10-10T12:00", "", "manual"
    )


def test_guest_core_data_persists_and_other_browser_is_isolated(tmp_path: Path) -> None:
    app = app_for(tmp_path / "guest.db")
    with TestClient(app) as first:
        session = guest(first)
        assert session["mode"] == "guest"
        assert first.post("/api/lessons", json=lesson()).status_code == 201
        assert first.post("/api/deadlines", json=deadline()).status_code == 201
        reloaded = first.get("/api/bootstrap").json()
        assert reloaded["session"]["mode"] == "guest"
        assert [row["subject"] for row in reloaded["lessons"]] == ["Гостевая математика"]
        assert [row["title"] for row in reloaded["deadlines"]] == ["Гостевой дедлайн"]

        with TestClient(app) as second:
            second_session = guest(second)
            assert second_session["user"]["id"] != session["user"]["id"]
            isolated = second.get("/api/bootstrap").json()
            assert isolated["lessons"] == []
            assert isolated["deadlines"] == []


def test_guest_is_blocked_from_ai_admin_and_cross_site_session_creation(tmp_path: Path) -> None:
    app = app_for(tmp_path / "gates.db")
    with TestClient(app) as client:
        assert client.post(
            "/api/auth/guest", headers={"Sec-Fetch-Site": "cross-site"}
        ).status_code == 403
        client.cookies.set(
            SESSION_COOKIE, "attacker-chosen", domain="testserver.local", path="/"
        )
        issued = guest(client)
        assert client.cookies.get(
            SESSION_COOKIE, domain="testserver.local", path="/"
        ) != "attacker-chosen"
        assert issued["user"]["id"] != "attacker-chosen"
        assert client.get("/api/student-ai/entitlement").status_code == 403
        assert client.get("/api/admin/overview").status_code == 403


def test_guest_link_preserves_data_and_logout_creates_isolated_guest(tmp_path: Path) -> None:
    app = app_for(tmp_path / "link.db")
    app.state.oidc.exchange = Mock(return_value={
        "telegram_id": "8247777174", "username": "owner", "display_name": "Owner",
    })
    with TestClient(app) as client:
        guest_session = guest(client)
        client.post("/api/lessons", json=lesson("До входа"))
        start = client.post("/api/auth/telegram/start").json()
        from urllib.parse import parse_qs, urlsplit
        state = parse_qs(urlsplit(start["url"]).query)["state"][0]
        callback = client.get(
            f"/api/auth/telegram/callback?state={state}&code=fixture", follow_redirects=False
        )
        assert "connected" in callback.headers["location"]
        authenticated = client.get("/api/bootstrap").json()
        assert authenticated["session"]["mode"] == "telegram"
        assert authenticated["session"]["user"]["id"] == guest_session["user"]["id"]
        assert authenticated["session"]["user"]["role"] == "admin"
        assert [row["subject"] for row in authenticated["lessons"]] == ["До входа"]

        client.headers["X-CSRF-Token"] = authenticated["session"]["csrf_token"]
        old_cookie = client.cookies.get(SESSION_COOKIE)
        assert client.post("/api/auth/logout").status_code == 204
        fresh = guest(client)
        assert fresh["user"]["id"] != authenticated["session"]["user"]["id"]
        assert client.get("/api/bootstrap").json()["lessons"] == []
        client.cookies.set(SESSION_COOKIE, old_cookie)
        assert client.get("/api/bootstrap").status_code == 401


def test_existing_account_merge_keeps_account_settings_and_entitlement(tmp_path: Path) -> None:
    app = app_for(tmp_path / "merge.db")
    database = app.state.database
    database.initialize()
    account = database.telegram_login_user("777", "student", "Student")
    database.update_preferences(account["id"], "dark", "day", "week", ["room"])
    add_deadline(database, account["id"], "Дубликат")
    with database.connection() as db:
        now = database._now()
        db.execute(
            """INSERT INTO ai_entitlements
            (user_id, balance, unlimited, free_trial_available, source, created_at, updated_at)
            VALUES (?, 5, 0, 0, 'telegram', ?, ?)""",
            (account["id"], now, now),
        )

    guest_user = database.create_user("Гость")
    database.update_preferences(guest_user["id"], "light", "week", "day", ["teacher"])
    database.add_lesson(guest_user["id"], lesson("На госте"))
    add_deadline(database, guest_user["id"], "Дубликат")
    add_deadline(database, guest_user["id"], "Уникальный")
    with database.connection() as db:
        now = database._now()
        db.execute(
            """INSERT INTO ai_entitlements
            (user_id, balance, unlimited, free_trial_available, source, created_at, updated_at)
            VALUES (?, 99, 1, 1, 'guest-fixture', ?, ?)""",
            (guest_user["id"], now, now),
        )

    merged = database.merge_guest_with_telegram(
        guest_user["id"], "777", "student", "Student"
    )
    assert merged["id"] == account["id"]
    assert [row["subject"] for row in database.lessons(account["id"])] == ["На госте"]
    assert sorted(row["title"] for row in database.deadlines(account["id"])) == ["Дубликат", "Уникальный"]
    assert database.preferences(account["id"])["theme"] == "dark"
    assert app.state.entitlements.get_balance(account["id"])["balance"] == 5


def test_frontend_bootstraps_guest_without_blocking_login(tmp_path: Path) -> None:
    source = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    init_source = source[source.index("async function init()") : source.index("document.addEventListener(\"DOMContentLoaded\",init)")]
    assert 'api("/api/auth/guest",{method:"POST"})' in init_source
    assert "showLogin()" not in init_source
