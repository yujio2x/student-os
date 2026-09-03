"""Telegram Authorization Code + PKCE. No tokens/profile payloads in logs."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from urllib.parse import urlencode, urlsplit

import httpx
import jwt

ISSUER = "https://oauth.telegram.org"
LOGIN_COOKIE = "student_os_telegram_login"


class OIDCError(ValueError):
    pass


class TelegramOIDC:
    def __init__(self, database, config):
        self.database = database
        self.config = config
        self.keys = jwt.PyJWKClient(ISSUER + "/.well-known/jwks.json", timeout=5)

    @property
    def configured(self):
        url = urlsplit(self.config.telegram_redirect_uri)
        return bool(self.config.telegram_client_id and self.config.telegram_client_secret
                    and url.scheme == "https" and url.hostname and not url.username
                    and not url.password and not url.query and not url.fragment
                    and url.path == "/api/auth/telegram/callback")

    def initialize(self):
        with self.database.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS telegram_login_attempts (
                state_hash TEXT PRIMARY KEY, browser_hash TEXT NOT NULL,
                verifier TEXT NOT NULL, expires_at INTEGER NOT NULL,
                session_hash TEXT NOT NULL, target_user_id TEXT)""")

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def begin(self, session_hash="", target_user_id=None):
        if not self.configured:
            raise OIDCError("not_configured")
        state, browser, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        now = int(time.time())
        with self.database.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM telegram_login_attempts WHERE expires_at<?", (now,))
            # Bound unauthenticated outstanding state; retry after expiry when flooded.
            if db.execute("SELECT COUNT(*) FROM telegram_login_attempts").fetchone()[0] >= 1000:
                raise OIDCError("busy")
            db.execute("INSERT INTO telegram_login_attempts VALUES (?,?,?,?,?,?)",
                       (self.digest(state), self.digest(browser), verifier, now + 300, session_hash, target_user_id))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        url = ISSUER + "/auth?" + urlencode({"client_id": self.config.telegram_client_id,
            "redirect_uri": self.config.telegram_redirect_uri, "response_type": "code",
            "scope": "openid profile", "state": state, "code_challenge": challenge,
            "code_challenge_method": "S256"})
        return url, browser

    def consume(self, state, browser, session_hash):
        if not 16 <= len(state) <= 128 or not 16 <= len(browser) <= 128:
            raise OIDCError("expired")
        with self.database.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM telegram_login_attempts WHERE state_hash=?",
                             (self.digest(state),)).fetchone()
            if (not row or row["expires_at"] < time.time()
                    or not secrets.compare_digest(row["browser_hash"], self.digest(browser))
                    or not secrets.compare_digest(row["session_hash"], session_hash)):
                raise OIDCError("expired")
            db.execute("DELETE FROM telegram_login_attempts WHERE state_hash=?", (self.digest(state),))
        return dict(row)

    def exchange(self, code, verifier):
        if not code or len(code) > 4096:
            raise OIDCError("invalid")
        try:
            with httpx.Client(timeout=10, follow_redirects=False) as client:
                with client.stream("POST", ISSUER + "/token",
                        auth=(self.config.telegram_client_id, self.config.telegram_client_secret),
                        data={"grant_type": "authorization_code", "code": code,
                              "redirect_uri": self.config.telegram_redirect_uri,
                              "client_id": self.config.telegram_client_id, "code_verifier": verifier}) as response:
                    response.raise_for_status()
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        if len(raw) + len(chunk) > 65536:
                            raise OIDCError("invalid")
                        raw.extend(chunk)
            token = json.loads(raw)["id_token"]
            return self.verify_token(token)
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            raise OIDCError("unavailable") from None

    def verify_token(self, token):
        try:
            if not isinstance(token, str) or len(token) > 16384:
                raise OIDCError("invalid")
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256"],
                audience=self.config.telegram_client_id, issuer=ISSUER,
                options={"require": ["iss", "aud", "sub", "exp", "iat", "id"]})
            if abs(time.time() - claims["iat"]) > 300:
                raise OIDCError("expired")
            telegram_id = claims["id"]
            if type(telegram_id) is not int or telegram_id <= 0:
                raise OIDCError("invalid")
            return {"telegram_id": str(telegram_id),
                    "username": str(claims.get("preferred_username", ""))[:80],
                    "display_name": str(claims.get("name", ""))[:160]}
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise OIDCError("invalid") from None
