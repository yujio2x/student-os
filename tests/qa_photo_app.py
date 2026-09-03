"""Explicit local browser fixture. Never point it at a production database."""
from pathlib import Path

from app.config import Settings
from app.main import create_app
from test_photo_service import Engine


def fixture_app():
    app = create_app(Settings(Path("data/photo-browser-fixture.db"), "", "demo", dev_admin_enabled=True))
    db = app.state.database
    db.initialize()
    user = db.ensure_local_user()
    db.link_telegram_identity(user["id"], "8240099", "photo_fixture", "Photo fixture")
    engine = Engine()
    engine.client = object()
    app.state.photo.engine = engine
    # Bootstrap's availability reads the original study instance, not engine calls.
    app.state.study.client = object()
    return app
