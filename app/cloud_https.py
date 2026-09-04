"""Heroku-only HTTPS boundary. Router overwrites X-Forwarded-Proto.

Do not install behind an arbitrary proxy without verifying the same trust contract.
"""
from urllib.parse import urlsplit
from starlette.datastructures import URL
from starlette.responses import RedirectResponse


class HerokuHTTPS:
    def __init__(self, application, canonical_url):
        parsed = urlsplit(canonical_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("HTTPS canonical origin required")
        self.application = application
        self.host = parsed.netloc

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            proto = dict(scope.get("headers", [])).get(b"x-forwarded-proto", b"")
            if proto != b"https":
                url = URL(scope=scope).replace(scheme="https", netloc=self.host)
                response = RedirectResponse(str(url), status_code=307,
                                            headers={"Cache-Control":"no-store"})
                await response(scope, receive, send)
                return
        await self.application(scope, receive, send)
