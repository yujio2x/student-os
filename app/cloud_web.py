"""Production entry point with opt-in, content-free error reporting."""
from app.observability import initialize, report
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
