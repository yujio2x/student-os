from __future__ import annotations

import json
import secrets
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.bridge_auth import BridgeAuthenticator
from app.config import Settings
from app.main import create_app


SECRET = "integration-test-bridge-secret"


class SpyStudy:
    client = object()

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def analyze(self, assignment: str, subject: str = "", title: str = ""):
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic outage")

        class Result:
            @staticmethod
            def to_dict() -> dict:
                return {
                    "subject": "Алгоритмы",
                    "assignment_title": "Единый контракт",
                    "analysis": "Понимание",
                    "explanation": "Решение",
                    "approach": ["Шаг"],
                    "checks": ["Проверка"],
                    "how_to_defend": "Объяснение для защиты",
                    "defense_questions": ["Почему?"],
                    "pitfalls": ["Слепое копирование"],
                    "suggested_due_at": None,
                    "mode": "fixture",
                }

            @staticmethod
            def usage() -> tuple[int, int]:
                return 21, 34

        return Result()


def bridge_app(path: Path):
    return create_app(
        Settings(
            path, "", "gpt-5.6-luna", entitlement_source="core",
            bot_bridge_secret=SECRET,
        )
    )


def telegram(telegram_user_id: int = 8240001) -> dict:
    return {
        "telegram_user_id": telegram_user_id,
        "username": "student_test",
        "display_name": "Әлия Тест",
    }


def signed_request(payload: dict, *, secret: str = SECRET, timestamp: int | None = None,
                   path: str = "/api/internal/v1/identity/resolve"):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    created = int(time.time()) if timestamp is None else timestamp
    nonce = secrets.token_urlsafe(18)
    return body, {
        "Content-Type": "application/json",
        "X-Bridge-Timestamp": str(created),
        "X-Bridge-Nonce": nonce,
        "X-Bridge-Signature": BridgeAuthenticator.signature(
            secret, created, nonce, body, path
        ),
    }


def bridge_post(client: TestClient, path: str, payload: dict):
    body, headers = signed_request(payload, path=path)
    return client.post(path, content=body, headers=headers)


def test_same_telegram_identity_resolves_to_one_internal_user(tmp_path: Path) -> None:
    app = bridge_app(tmp_path / "identity.db")
    payload = {"telegram": telegram()}
    with TestClient(app) as client:
        first = bridge_post(client, "/api/internal/v1/identity/resolve", payload)
        second = bridge_post(client, "/api/internal/v1/identity/resolve", payload)
        assert first.status_code == second.status_code == 200
        assert first.json()["user"]["id"] == second.json()["user"]["id"]
        assert first.json()["entitlement"]["free_trial_available"] is True


def test_products_and_telegram_star_payments_are_core_validated(tmp_path: Path) -> None:
    app = bridge_app(tmp_path / "payments.db")
    with TestClient(app) as client:
        products = bridge_post(client, "/api/internal/v1/products", {}).json()["products"]
        assert {(item["stars"], item["credits"]) for item in products} == {(25, 1), (100, 5)}

        payment = {
            "telegram": telegram(), "charge_id": "charge-001",
            "product_id": "task_help_5_v1", "stars_paid": 100,
        }
        first = bridge_post(client, "/api/internal/v1/payments/telegram-stars", payment)
        duplicate = bridge_post(client, "/api/internal/v1/payments/telegram-stars", payment)
        assert first.status_code == duplicate.status_code == 200
        assert first.json()["entitlement"]["balance"] == 5
        assert duplicate.json()["entitlement"]["balance"] == 5
        assert duplicate.json()["payment"]["duplicate"] is True

        wrong = bridge_post(
            client, "/api/internal/v1/payments/telegram-stars",
            {**payment, "charge_id": "charge-002", "stars_paid": 99},
        )
        unknown = bridge_post(
            client, "/api/internal/v1/payments/telegram-stars",
            {**payment, "charge_id": "charge-003", "product_id": "attacker-product"},
        )
        assert wrong.status_code == unknown.status_code == 422


def test_bridge_text_uses_canonical_contract_and_shared_trial(tmp_path: Path) -> None:
    app = bridge_app(tmp_path / "study.db")
    spy = SpyStudy()
    app.state.study = spy
    payload = {
        "telegram": telegram(), "assignment": "Реши задачу",
        "subject": "Алгоритмы", "title": "Лабораторная", "request_id": "bridge-ai-001",
    }
    with TestClient(app) as client:
        result = bridge_post(client, "/api/internal/v1/study/text", payload)
        duplicate = bridge_post(client, "/api/internal/v1/study/text", payload)
        assert result.status_code == 200
        assert duplicate.status_code == 409
        assert spy.calls == 1
        assert result.json()["result"]["how_to_defend"] == "Объяснение для защиты"
        assert result.json()["entitlement"]["free_trial_available"] is False
        with app.state.database.connection() as db:
            usage = db.execute(
                """SELECT status, entitlement_source, input_tokens, output_tokens
                FROM ai_credit_reservations WHERE request_id='bridge-ai-001'"""
            ).fetchone()
        assert tuple(usage) == ("committed", "trial", 21, 34)


def test_bridge_failure_releases_shared_trial(tmp_path: Path) -> None:
    app = bridge_app(tmp_path / "failure.db")
    app.state.study = SpyStudy(fail=True)
    payload = {
        "telegram": telegram(), "assignment": "Реши задачу",
        "request_id": "bridge-failure-001",
    }
    with TestClient(app) as client:
        assert bridge_post(client, "/api/internal/v1/study/text", payload).status_code == 502
        state = bridge_post(
            client, "/api/internal/v1/entitlement", {"telegram": telegram()}
        ).json()["entitlement"]
        assert state["free_trial_available"] is True


def test_bridge_rejects_bad_hmac_stale_replay_and_tampering(tmp_path: Path) -> None:
    app = bridge_app(tmp_path / "security.db")
    path = "/api/internal/v1/identity/resolve"
    payload = {"telegram": telegram()}
    with TestClient(app) as client:
        bad_body, bad_headers = signed_request(payload, secret="wrong-secret")
        assert client.post(path, content=bad_body, headers=bad_headers).status_code == 401

        stale_body, stale_headers = signed_request(payload, timestamp=int(time.time()) - 301)
        assert client.post(path, content=stale_body, headers=stale_headers).status_code == 401

        body, headers = signed_request(payload)
        assert client.post(path, content=body, headers=headers).status_code == 200
        assert client.post(path, content=body, headers=headers).status_code == 401

        tampered = body.replace(b"8240001", b"8240002")
        assert client.post(path, content=tampered, headers=headers).status_code == 401


def test_unconfigured_bridge_fails_closed(tmp_path: Path) -> None:
    app = create_app(Settings(tmp_path / "off.db", "", "gpt-5.6-luna"))
    with TestClient(app) as client:
        body, headers = signed_request({"telegram": telegram()})
        response = client.post(
            "/api/internal/v1/identity/resolve", content=body, headers=headers
        )
        assert response.status_code == 503


def test_signature_is_endpoint_bound_and_body_limit_precedes_json_parsing(tmp_path):
    app = bridge_app(tmp_path / "attack.db")
    with TestClient(app) as client:
        body, headers = signed_request({"telegram": telegram()})
        assert client.post("/api/internal/v1/entitlement", content=body, headers=headers).status_code == 401
        assert client.post("/api/internal/v1/identity/resolve", content=body, headers=headers).status_code == 200
        assert client.post("/api/internal/v1/products", content=b"x" * 65537).status_code == 413
        for key, value in (("X-Bridge-Timestamp", "9" * 5000),
                           ("X-Bridge-Signature", "z" * 64)):
            invalid = {**headers, key: value}
            assert client.post("/api/internal/v1/identity/resolve", content=body, headers=invalid).status_code == 401


def test_auth_rejects_non_ascii_header_and_rate_limit(tmp_path):
    from app.bridge_auth import BridgeAuthError, BridgeRateLimitError
    import pytest
    app = bridge_app(tmp_path / "headers.db")
    with TestClient(app):
        auth = BridgeAuthenticator(app.state.database, SECRET, max_requests_per_minute=1)
        now = int(time.time())
        for timestamp, nonce, signature in (("١٢٣", "a" * 20, "a" * 64),
                                              (str(now), "ә" * 20, "a" * 64),
                                              (str(now), "a" * 20, "ә" * 64)):
            with pytest.raises(BridgeAuthError):
                auth.verify(timestamp, nonce, signature, b"{}")
        for number in range(2):
            nonce = f"rate-test-nonce-{number:04}"
            signature = auth.signature(SECRET, now, nonce, b"{}")
            if number == 0:
                auth.verify(str(now), nonce, signature, b"{}")
            else:
                with pytest.raises(BridgeRateLimitError):
                    auth.verify(str(now), nonce, signature, b"{}")
