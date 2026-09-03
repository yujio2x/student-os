from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.database import Database


SESSION_COOKIE = "student_os_session"


@dataclass(frozen=True)
class IssuedSession:
    token: str
    csrf_token: str
    expires_at: str


class SessionService:
    """Opaque server-side sessions. Only a SHA-256 token digest is persisted."""

    def __init__(self, database: Database, ttl_hours: int) -> None:
        self.database = database
        self.ttl_hours = ttl_hours

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue(self, user_id: str) -> IssuedSession:
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        expires_at = (
            datetime.now(UTC) + timedelta(hours=self.ttl_hours)
        ).isoformat(timespec="seconds")
        self.database.create_session(
            self.token_hash(token), user_id, csrf_token, expires_at
        )
        return IssuedSession(token, csrf_token, expires_at)

    def resolve(self, token: str | None) -> dict | None:
        if not token:
            return None
        return self.database.session(self.token_hash(token))

    def revoke(self, token: str | None) -> bool:
        if not token:
            return False
        return self.database.revoke_session(self.token_hash(token))
