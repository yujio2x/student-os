from __future__ import annotations

import hashlib
import hmac
import threading
import time
from collections import deque

from app.database import Database


class BridgeAuthError(ValueError):
    pass


class BridgeRateLimitError(BridgeAuthError):
    pass


class BridgeAuthenticator:
    """HMAC service authentication with freshness, replay and a bounded request rate."""

    def __init__(
        self, database: Database, secret: str, max_age_seconds: int = 300,
        max_requests_per_minute: int = 120,
    ) -> None:
        self.database = database
        self.secret = secret.encode("utf-8")
        self.max_age_seconds = max_age_seconds
        self.max_requests_per_minute = max_requests_per_minute
        self._recent: deque[int] = deque()
        self._lock = threading.Lock()

    @staticmethod
    def signature(secret: str, timestamp: int, nonce: str, body: bytes) -> str:
        message = str(timestamp).encode() + b"." + nonce.encode() + b"." + body
        return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

    def verify(self, timestamp: str, nonce: str, signature: str, body: bytes) -> None:
        if not self.secret:
            raise BridgeAuthError("bridge is not configured")
        if len(body) > 64 * 1024:
            raise BridgeAuthError("bridge payload too large")
        if not timestamp.isdigit() or not (16 <= len(nonce) <= 128):
            raise BridgeAuthError("invalid bridge authentication")
        now = int(time.time())
        supplied_time = int(timestamp)
        if abs(now - supplied_time) > self.max_age_seconds:
            raise BridgeAuthError("stale bridge request")
        if len(signature) != 64:
            raise BridgeAuthError("invalid bridge authentication")
        expected = hmac.new(
            self.secret,
            timestamp.encode() + b"." + nonce.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise BridgeAuthError("invalid bridge authentication")
        with self._lock:
            cutoff = now - 60
            while self._recent and self._recent[0] <= cutoff:
                self._recent.popleft()
            if len(self._recent) >= self.max_requests_per_minute:
                raise BridgeRateLimitError("bridge rate limit exceeded")
            self._recent.append(now)
        if not self.database.consume_bridge_nonce(nonce):
            raise BridgeAuthError("bridge request replayed")
