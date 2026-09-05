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
from app.observability import report

ISSUER = "https://oauth.telegram.org"
LOGIN_COOKIE = "student_os_telegram_login"
CLOCK_SKEW_SECONDS = 30


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
        if getattr(self.database, "is_postgres", False):
            return
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
                       (self.digest(state), self.digest(browser), verifier,
                        now + self.config.telegram_auth_max_age_seconds,
                        session_hash, target_user_id))
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
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            report("oidc_exchange_failed")
            raise OIDCError("unavailable") from None
        try:
            return self.verify_token(token)
        except OIDCError:
            raise

    def verify_token(self, token):
        if not isinstance(token, str) or len(token) > 16384:
            report("oidc_verify_claims_failed")
            raise OIDCError("invalid")
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
        except (jwt.PyJWKClientError, jwt.DecodeError, ValueError, TypeError, KeyError):
            report("oidc_verify_key_failed")
            raise OIDCError("invalid") from None
        try:
            claims = jwt.decode(token, key, algorithms=["RS256"],
                audience=self.config.telegram_client_id, issuer=ISSUER,
                leeway=CLOCK_SKEW_SECONDS,
                options={"require": ["iss", "aud", "sub", "exp", "iat", "id"]})
        except jwt.InvalidSignatureError:
            report("oidc_verify_signature_failed")
            raise OIDCError("invalid") from None
        except jwt.InvalidAlgorithmError:
            report("oidc_verify_algorithm_failed")
            raise OIDCError("invalid") from None
        except jwt.InvalidAudienceError:
            report("oidc_verify_audience_failed")
            raise OIDCError("invalid") from None
        except jwt.InvalidIssuerError:
            report("oidc_verify_issuer_failed")
            raise OIDCError("invalid") from None
        except (jwt.ExpiredSignatureError, jwt.ImmatureSignatureError,
                jwt.InvalidIssuedAtError):
            report("oidc_verify_lifetime_failed")
            raise OIDCError("expired") from None
        except jwt.PyJWTError:
            report("oidc_verify_claims_failed")
            raise OIDCError("invalid") from None
        if (type(claims["iat"]) not in {int, float}
                or abs(time.time() - claims["iat"]) >
                self.config.telegram_auth_max_age_seconds + CLOCK_SKEW_SECONDS):
            report("oidc_verify_lifetime_failed")
            raise OIDCError("expired")
        raw_id = claims["id"]
        if type(raw_id) is int:
            telegram_id = raw_id
        elif (type(raw_id) is str and 1 <= len(raw_id) <= 19
              and raw_id.isascii() and raw_id.isdecimal()
              and raw_id[0] != "0"):
            telegram_id = int(raw_id)
        else:
            report("oidc_verify_identity_failed")
            raise OIDCError("invalid")
        if not 0 < telegram_id < 2 ** 63:
            report("oidc_verify_identity_failed")
            raise OIDCError("invalid")
        return {"telegram_id": str(telegram_id),
                "username": str(claims.get("preferred_username", ""))[:80],
                "display_name": str(claims.get("name", ""))[:160]}
