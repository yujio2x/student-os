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
    redirect_uri = os.getenv("TELEGRAM_REDIRECT_URI")
    # Fail with a diagnosable message instead of a KeyError crash loop on deploy.
    if not redirect_uri:
        raise RuntimeError(
            "TELEGRAM_REDIRECT_URI is required in cloud production/staging: "
            "set it to the public HTTPS origin before deploying"
        )
    application = HerokuHTTPS(application, redirect_uri)
