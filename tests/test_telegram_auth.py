from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE
from app.config import Settings
from app.main import create_app


BOT_TOKEN = "123456:test-only-token"


def signed_payload(auth_date: int, telegram_id: int = 777, **changes) -> dict:
    payload = {
        "id": telegram_id,
        "first_name": "Әлия",
        "last_name": "Тест",
        "username": "aliya_test",
        "photo_url": "",
        "auth_date": auth_date,
    }
    payload.update(changes)
    check = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    payload["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return payload


def telegram_app(path: Path):
    return create_app(
        Settings(path, "", "gpt-5.6-luna", telegram_bot_token=BOT_TOKEN)
    )


def dev_login(client: TestClient) -> dict:
    data = client.post("/api/auth/dev-login").json()
    client.headers["X-CSRF-Token"] = data["csrf_token"]
    return data


def test_verified_telegram_creates_internal_user_and_rejects_replay(tmp_path: Path) -> None:
    app = telegram_app(tmp_path / "telegram.db")
    now = int(time.time())
    payload = signed_payload(now)
    with TestClient(app) as client:
        response = client.post("/api/auth/telegram/login", json=payload)
        assert response.status_code == 200
        user_id = response.json()["user"]["id"]
        assert user_id != str(payload["id"])
        assert client.get("/api/auth/session").status_code == 200
        assert app.state.database.telegram_identity(user_id)["provider_user_id"] == "777"

        assert client.post("/api/auth/telegram/login", json=payload).status_code == 409


def test_forged_stale_future_and_unconfigured_payloads_fail(tmp_path: Path) -> None:
    app = telegram_app(tmp_path / "invalid.db")
    now = int(time.time())
    with TestClient(app) as client:
        forged = signed_payload(now)
        forged["username"] = "attacker"
        assert client.post("/api/auth/telegram/login", json=forged).status_code == 401
        assert client.post(
            "/api/auth/telegram/login", json=signed_payload(now - 301)
        ).status_code == 401
        assert client.post(
            "/api/auth/telegram/login", json=signed_payload(now + 31)
        ).status_code == 401

    no_token = create_app(Settings(tmp_path / "no-token.db", "", "gpt-5.6-luna"))
    with TestClient(no_token) as client:
        assert client.post(
            "/api/auth/telegram/login", json=signed_payload(now)
        ).status_code == 503


def test_link_is_idempotent_but_conflicting_user_is_denied(tmp_path: Path) -> None:
    app = telegram_app(tmp_path / "links.db")
    now = int(time.time())
    with TestClient(app) as client:
        owner = dev_login(client)
        first = client.post("/api/account/telegram/link", json=signed_payload(now))
        assert first.status_code == 200
        second = client.post(
            "/api/account/telegram/link",
            json=signed_payload(now + 1, username="aliya_new"),
        )
        assert second.status_code == 200
        assert second.json()["username"] == "aliya_new"
        assert client.delete("/api/account/telegram/link").status_code == 409

        other = app.state.database.create_user("Other")
        issued = app.state.sessions.issue(other["id"])
        client.cookies.set(
            SESSION_COOKIE, issued.token, domain="testserver.local", path="/"
        )
        client.headers["X-CSRF-Token"] = issued.csrf_token
        conflict = client.post(
            "/api/account/telegram/link",
            json=signed_payload(now + 2, first_name="Conflict"),
        )
        assert conflict.status_code == 409
        assert app.state.database.telegram_identity(owner["user"]["id"])["provider_user_id"] == "777"
