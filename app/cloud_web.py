"""Production entry point with opt-in, content-free error reporting."""
import os
from app.observability import initialize, report
from app.cloud_https import HerokuHTTPS
from app.main import app

initialize("core")


class OperationalErrors:
    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        try:
            await self.application(scope, receive, send)
        except Exception:
            if scope["type"] == "http":
                report("core_unhandled")
            raise


application = OperationalErrors(app)
if os.getenv("DYNO") and os.getenv("APP_ENV") in {"production", "staging"}:
    application = HerokuHTTPS(application, os.environ["TELEGRAM_REDIRECT_URI"])
