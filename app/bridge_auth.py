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


class BridgeBodyLimitMiddleware:
    """Bound bytes before FastAPI parses the JSON body or resolves dependencies."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/internal/"):
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > 64 * 1024:
                await send({"type": "http.response.start", "status": 413,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"detail":"Bridge payload too large"}'})
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


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
    def signature(secret: str, timestamp: int, nonce: str, body: bytes,
                  path: str = "/api/internal/v1/identity/resolve") -> str:
        message = b"v2.POST." + path.encode() + b"." + str(timestamp).encode() + b"." + nonce.encode() + b"." + body
        return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

    def verify(self, timestamp: str, nonce: str, signature: str, body: bytes,
               path: str = "/api/internal/v1/identity/resolve") -> None:
        if not self.secret:
            raise BridgeAuthError("bridge is not configured")
        if len(body) > 64 * 1024:
            raise BridgeAuthError("bridge payload too large")
        if (not timestamp.isascii() or not timestamp.isdigit() or len(timestamp) > 12
                or not nonce.isascii() or not (16 <= len(nonce) <= 128)):
            raise BridgeAuthError("invalid bridge authentication")
        now = int(time.time())
        supplied_time = int(timestamp)
        if abs(now - supplied_time) > self.max_age_seconds:
            raise BridgeAuthError("stale bridge request")
        if len(signature) != 64 or any(c not in "0123456789abcdef" for c in signature):
            raise BridgeAuthError("invalid bridge authentication")
        expected = hmac.new(
            self.secret,
            b"v2.POST." + path.encode() + b"." + timestamp.encode() + b"." + nonce.encode() + b"." + body,
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
