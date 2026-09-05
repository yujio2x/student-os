import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch

import jwt
import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.telegram_oidc import ISSUER, LOGIN_COOKIE, OIDCError


def configured_app(tmp_path):
    return create_app(Settings(tmp_path / "oidc.db", "", "demo",
        telegram_client_id="1234", telegram_client_secret="fixture-only-secret",
        telegram_redirect_uri="https://example.test/api/auth/telegram/callback",
        owner_telegram_id="8247777174"))


def start(client, headers=None):
    response = client.post("/api/auth/telegram/start", headers=headers or {})
    assert response.status_code == 200
    query = parse_qs(urlsplit(response.json()["url"]).query)
    assert query["scope"] == ["openid profile"]
    assert query["code_challenge_method"] == ["S256"]
    assert "fixture-only-secret" not in response.text
    return query["state"][0]


def test_pkce_cookie_binding_replay_owner_and_logout(tmp_path):
    app = configured_app(tmp_path)
    app.state.oidc.exchange = Mock(return_value={"telegram_id": "8247777174", "username": "owner", "display_name": "Owner"})
    with TestClient(app) as client:
        state = start(client)
        browser = client.cookies.get(LOGIN_COOKIE)
        client.cookies.clear()
        invalid = client.get(f"/api/auth/telegram/callback?state={state}&code=fixture", follow_redirects=False)
        assert "expired" in invalid.headers["location"]
        app.state.oidc.exchange.assert_not_called()
        client.cookies.set(LOGIN_COOKIE, browser)
        result = client.get(f"/api/auth/telegram/callback?state={state}&code=fixture", follow_redirects=False)
        assert "connected" in result.headers["location"]
        session = client.get("/api/auth/session").json()
        assert session["user"]["role"] == "admin"
        assert client.get("/admin").status_code == 200
        assert result.headers["cache-control"] == "no-store"
        assert client.get(f"/api/auth/telegram/callback?state={state}&code=fixture", follow_redirects=False).headers["location"].endswith("expired#settings")
        assert app.state.oidc.exchange.call_count == 1
        assert client.post("/api/auth/logout", headers={"X-CSRF-Token": session["csrf_token"]}).status_code == 204
        assert client.get("/api/auth/session").status_code == 401


def test_link_requires_csrf_and_conflict_does_not_split_account(tmp_path):
    app = configured_app(tmp_path)
    with TestClient(app) as client:
        original = app.state.database.telegram_login_user("777", "student", "Student")
        local = client.post("/api/auth/dev-login").json()
        assert client.post("/api/auth/telegram/start").status_code == 403
        state = start(client, {"X-CSRF-Token": local["csrf_token"]})
        app.state.oidc.exchange = Mock(return_value={"telegram_id": "777", "username": "student", "display_name": "Student"})
        result = client.get(f"/api/auth/telegram/callback?state={state}&code=fixture", follow_redirects=False)
        assert "conflict" in result.headers["location"]
        assert client.get("/api/auth/session").json()["user"]["id"] == local["user"]["id"]
        assert app.state.database.telegram_login_user("777", "student", "Student")["id"] == original["id"]


def test_expired_cancelled_and_unconfigured(tmp_path):
    app = configured_app(tmp_path)
    with TestClient(app) as client:
        state = start(client)
        cancelled = client.get(f"/api/auth/telegram/callback?state={state}&error=access_denied", follow_redirects=False)
        assert "cancelled" in cancelled.headers["location"]
        state = start(client)
        with app.state.database.connection() as db:
            db.execute("UPDATE telegram_login_attempts SET expires_at=0")
        assert "expired" in client.get(f"/api/auth/telegram/callback?state={state}&code=x", follow_redirects=False).headers["location"]
    unconfigured = create_app(Settings(tmp_path / "off.db", "", "demo"))
    with TestClient(unconfigured) as client:
        assert not client.get("/api/auth/options").json()["telegram_login"]
        assert client.post("/api/auth/telegram/start").status_code == 503


def test_real_rs256_signature_claims_and_forgery(tmp_path):
    app = configured_app(tmp_path)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    app.state.oidc.keys = Mock()
    app.state.oidc.keys.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": "1234", "sub": "opaque-sub", "id": 777,
              "iat": now, "exp": now + 300, "name": "Әлия"}
    encode = lambda data: jwt.encode(data, key, algorithm="RS256")
    assert app.state.oidc.verify_token(encode(claims))["telegram_id"] == "777"
    assert app.state.oidc.verify_token(encode({**claims, "id": "8247777174"}))["telegram_id"] == "8247777174"
    for changes in ({"aud": "attacker"}, {"iss": "https://evil.test"}, {"exp": now - 1},
                    {"iat": now - 301}, {"id": -1}, {"id": True}, {"id": 7.0},
                    {"id": " 777"}, {"id": "+777"}, {"id": "00777"},
                    {"id": "9" * 20}):
        with pytest.raises(OIDCError):
            app.state.oidc.verify_token(encode({**claims, **changes}))
    with pytest.raises(OIDCError):
        app.state.oidc.verify_token(jwt.encode(claims, "synthetic-not-rsa-test-secret-long-enough", algorithm="HS256"))


def test_exchange_reports_only_allowlisted_failure_stage(tmp_path):
    app = configured_app(tmp_path)
    oidc = app.state.oidc
    with patch("app.telegram_oidc.httpx.Client", side_effect=httpx.ConnectError("private code")), \
         patch("app.telegram_oidc.report") as report:
        with pytest.raises(OIDCError):
            oidc.exchange("private-code", "private-verifier")
        report.assert_called_once_with("oidc_exchange_failed")
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.raise_for_status.return_value = None
    response.iter_bytes.return_value = [b'{"id_token":"private-token"}']
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.stream.return_value = response
    with patch("app.telegram_oidc.httpx.Client", return_value=client), \
         patch.object(oidc, "verify_token", side_effect=OIDCError("private claim")), \
         patch("app.telegram_oidc.report") as report:
        with pytest.raises(OIDCError):
            oidc.exchange("private-code", "private-verifier")
        report.assert_not_called()


def test_verify_reports_only_specific_safe_failure_categories(tmp_path):
    app = configured_app(tmp_path)
    oidc = app.state.oidc
    with patch.object(oidc.keys, "get_signing_key_from_jwt",
                      side_effect=jwt.PyJWKClientError("private jwks")), \
         patch("app.telegram_oidc.report") as report:
        with pytest.raises(OIDCError):
            oidc.verify_token("private-token")
        report.assert_called_once_with("oidc_verify_key_failed")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    oidc.keys = Mock()
    oidc.keys.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": "wrong", "sub": "opaque", "id": 777,
              "iat": now, "exp": now + 300}
    with patch("app.telegram_oidc.report") as report:
        with pytest.raises(OIDCError):
            oidc.verify_token(jwt.encode(claims, key, algorithm="RS256"))
        report.assert_called_once_with("oidc_verify_audience_failed")
