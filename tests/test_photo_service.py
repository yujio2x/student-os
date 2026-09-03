import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

from app.ai_service import StudyService
from app.database import Database
from app.entitlements import UnifiedEntitlementService, ReservationConflict
from app.photo_service import PhotoService, PhotoError, validate_photo


def image():
    stream = io.BytesIO()
    Image.new("RGB", (16, 16)).save(stream, format="PNG")
    return stream.getvalue()


class Engine(StudyService):
    def __init__(self):
        super().__init__("", "demo")
        self.calls = 0
        self.fail = False

    def recognize_photo(self, data, mime):
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic recognition outage")
        return ["1. Қазақша есеп x=1", "2. Реши y=2", "3. [неразборчиво]"], 12, 34

    def analyze(self, assignment, subject="", title=""):
        return self._demo_result(assignment, subject, title)


@pytest.fixture
def photo(tmp_path):
    db = Database(tmp_path / "photo.db")
    db.initialize()
    user = db.create_user("Photo fixture")["id"]
    entitlement = UnifiedEntitlementService(db)
    engine = Engine()
    service = PhotoService(db, entitlement, engine)
    service.initialize()
    return service, entitlement, engine, user


def test_validation_before_any_ai_and_trial_setup(photo):
    service, ledger, engine, user = photo
    for data, mime in ((b"not png", "image/png"), (image(), "image/jpeg"), (image(), "application/pdf"),
                       (b"x" * (6 * 1024 * 1024 + 1), "image/png")):
        with pytest.raises(PhotoError):
            service.quote(user, data, mime)
    assert engine.calls == 0
    quote = service.quote(user, image(), "image/png")
    assert quote["uses_trial"] and quote["credits"] == 0
    assert ledger.get_balance(user)["free_trial_available"]
    session = service.confirm(user, quote["quote_id"], image(), "image/png")
    assert not ledger.get_balance(user)["free_trial_available"]
    assert session["tasks"][0].startswith("1. Қазақша")
    with pytest.raises(PhotoError):
        service.confirm(user, quote["quote_id"], image(), "image/png")
    first = service.answer(user, session["session_id"], [0, 1], "photo-answer-1")
    assert first["how_to_defend"]
    service.answer(user, session["session_id"], [2], "photo-answer-2")
    assert ledger.get_balance(user)["balance"] == 0
    with pytest.raises(PhotoError):
        service.answer(user, session["session_id"], [0], "photo-answer-1")


def test_changed_quote_never_silently_charges_and_failure_refunds(photo):
    service, ledger, engine, user = photo
    quote = service.quote(user, image(), "image/png")
    ledger.reserve_credit(user, "another-interface")
    ledger.commit_usage("another-interface")
    with pytest.raises(ReservationConflict):
        service.confirm(user, quote["quote_id"], image(), "image/png")
    assert engine.calls == 0
    service.database.admin_adjust_credits(user, user, 5, "fixture", "photo-credit")
    quote = service.quote(user, image(), "image/png")
    assert quote["credits"] == 5
    engine.fail = True
    with pytest.raises(RuntimeError):
        service.confirm(user, quote["quote_id"], image(), "image/png")
    assert ledger.get_balance(user)["balance"] == 5


def test_concurrent_confirmation_ownership_expiry_and_purge(photo):
    service, ledger, engine, user = photo
    quote = service.quote(user, image(), "image/png")
    def confirm(_):
        try:
            return service.confirm(user, quote["quote_id"], image(), "image/png")
        except PhotoError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(confirm, [0, 1]))
    assert sum(r is not None for r in results) == 1
    assert engine.calls == 1
    session = next(r for r in results if r)
    other = service.database.create_user("Other")["id"]
    with pytest.raises(PhotoError):
        service.answer(other, session["session_id"], [0], "other-user-01")
    with pytest.raises(PhotoError):
        service.answer(user, session["session_id"], [999], "invalid-selection")
    with service.database.connection() as db:
        db.execute("UPDATE photo_sessions SET expires_at=0")
    with pytest.raises(PhotoError):
        service.answer(user, session["session_id"], [0], "expired-photo")
    with service.database.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM photo_sessions").fetchone()[0] == 0
