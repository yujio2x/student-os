from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE
from app.config import Settings
from app.main import create_app


def make_app(path: Path, source: str = "unconnected"):
    return create_app(
        Settings(path, "", "gpt-5.6-luna", entitlement_source=source)
    )


def use_identity(client: TestClient, app, user: dict) -> None:
    issued = app.state.sessions.issue(user["id"])
    client.cookies.set(
        SESSION_COOKIE, issued.token, domain="testserver.local", path="/"
    )
    client.headers["X-CSRF-Token"] = issued.csrf_token


def test_admin_routes_deny_normal_user_on_page_and_api(tmp_path: Path) -> None:
    app = make_app(tmp_path / "denied.db")
    with TestClient(app) as client:
        login = client.post("/api/auth/dev-login").json()
        client.headers["X-CSRF-Token"] = login["csrf_token"]
        assert client.get("/admin").status_code == 403
        assert client.get("/api/admin/overview").status_code == 403
        assert client.post(
            f"/api/admin/users/{login['user']['id']}/credits",
            json={"delta": 5, "reason": "forbidden", "request_id": "deny-request"},
        ).status_code == 403


def test_feedback_is_minimal_idempotent_and_aggregated(tmp_path: Path) -> None:
    app = make_app(tmp_path / "feedback.db")
    with TestClient(app) as client:
        login = client.post("/api/auth/dev-login").json()
        client.headers["X-CSRF-Token"] = login["csrf_token"]
        payload = {
            "kind": "product", "rating": "", "request_id": "feedback-001",
            "message": "<img src=x onerror=alert(1)> Нужен быстрый поиск",
        }
        assert client.post("/api/feedback", json=payload).status_code == 201
        assert client.post("/api/feedback", json=payload).status_code == 201
        assert client.post("/api/feedback", json={**payload, "message": ""}).status_code == 422

        admin = app.state.database.create_user("Owner", role="admin")
        use_identity(client, app, admin)
        overview = client.get("/api/admin/overview").json()
        assert overview["feedback_total"] == 1
        assert client.get("/api/admin/feedback").json()["feedback"][0]["message"] == payload["message"]
        assert "notes" not in client.get("/api/admin/users").text


def test_admin_credit_mutations_are_bounded_idempotent_and_audited(tmp_path: Path) -> None:
    app = make_app(tmp_path / "admin.db", source="local")
    with TestClient(app) as client:
        target = app.state.database.create_user("Target")
        admin = app.state.database.create_user("Owner", role="admin")
        use_identity(client, app, admin)

        path = f"/api/admin/users/{target['id']}/credits"
        body = {"delta": 5, "reason": "Beta support", "request_id": "credit-action-1"}
        csrf = client.headers.pop("X-CSRF-Token")
        assert client.post(path, json=body).status_code == 403
        client.headers["X-CSRF-Token"] = csrf
        assert client.post(path, json=body).json()["balance"] == 5
        assert client.post(path, json=body).json()["balance"] == 5
        assert client.post(path, json={**body, "delta": 1}).status_code == 409
        assert client.post(
            path, json={"delta": -6, "reason": "Too much", "request_id": "credit-action-2"}
        ).status_code == 409
        assert client.post(
            path, json={"delta": 1, "reason": "x", "request_id": "credit-action-3"}
        ).status_code == 422
        assert client.post(
            "/api/admin/users/missing/credits",
            json={"delta": 1, "reason": "Missing user", "request_id": "credit-missing"},
        ).status_code == 404

        unlimited = client.post(
            f"/api/admin/users/{target['id']}/unlimited",
            json={"enabled": True, "reason": "Approved beta", "request_id": "unlimited-1"},
        )
        assert unlimited.json()["unlimited"] is True
        actions = client.get("/api/admin/actions").json()
        assert actions["total"] == 2
        assert {item["action"] for item in actions["actions"]} == {
            "credits_adjusted", "unlimited_changed",
        }
        detail = client.get(f"/api/admin/users/{target['id']}").json()
        assert len(detail["actions"]) == 2
        assert detail["free_trial_available"] == 1
        assert "lessons" not in detail and "deadlines" not in detail

        with app.state.database.connection() as db:
            db.execute(
                "UPDATE ai_entitlements SET free_trial_available=0 WHERE user_id=?",
                (target["id"],),
            )
        restored = client.post(
            f"/api/admin/users/{target['id']}/trial",
            json={"reason": "Restore support attempt", "request_id": "trial-action-1"},
        )
        assert restored.json()["free_trial_available"] is True
        assert client.post(
            f"/api/admin/users/{target['id']}/trial",
            json={"reason": "Restore support attempt", "request_id": "trial-action-1"},
        ).json()["free_trial_available"] is True
        assert app.state.database.admin_actions(None, 10, 0)["total"] == 3


def test_unconnected_credit_source_disables_admin_writes(tmp_path: Path) -> None:
    app = make_app(tmp_path / "unconnected.db")
    with TestClient(app) as client:
        target = app.state.database.create_user("Target")
        admin = app.state.database.create_user("Owner", role="admin")
        use_identity(client, app, admin)
        response = client.post(
            f"/api/admin/users/{target['id']}/credits",
            json={"delta": 1, "reason": "Not connected", "request_id": "blocked-credits"},
        )
        assert response.status_code == 409
        assert app.state.database.admin_actions(None, 10, 0)["total"] == 0


def test_admin_static_client_uses_text_content_not_inner_html(tmp_path: Path) -> None:
    app = make_app(tmp_path / "static.db")
    with TestClient(app) as client:
        script = client.get("/static/admin.js").text
        assert "textContent" in script
        assert "innerHTML" not in script
