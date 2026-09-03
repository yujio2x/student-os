import json

import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.auth import SESSION_COOKIE


@pytest.fixture
def setup(tmp_path):
    app = create_app(Settings(tmp_path / "restore.db", "", "demo"))
    with TestClient(app) as client:
        session = client.post("/api/auth/dev-login").json()
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        yield app, client, session


def preview(client, raw):
    return client.post("/api/restore/preview", files={"file": ("backup.json", raw, "application/json")})


def confirm(client, raw, identifier, consent="true"):
    return client.post("/api/restore/confirm", data={"preview_id": identifier, "confirm_replace": consent},
                       files={"file": ("backup.json", raw, "application/json")})


def test_owned_atomic_roundtrip_and_no_implicit_write(setup):
    app, client, session = setup
    user = session["user"]["id"]
    other = app.state.database.create_user("Other")["id"]
    app.state.database.add_deadline(other, "private", "", "2026-01-01T10:00", "", "manual")
    raw = client.get("/api/export").content
    document = json.loads(raw)
    document["lessons"] = []
    document["deadlines"] = [{"id": 999, "title": "Әлия дедлайн", "subject": "Тест", "due_at": "2020-01-01T10:00", "description": "Unicode 😀", "source": "ai-study", "completed": 1}]
    raw = json.dumps(document).encode()
    before = app.state.database.lessons(user)
    result = preview(client, raw)
    assert result.status_code == 200
    identifier = result.json()["preview_id"]
    assert app.state.database.lessons(user) == before
    assert confirm(client, raw, identifier, "false").status_code == 422
    assert confirm(client, raw, identifier).status_code == 200
    assert app.state.database.lessons(user) == []
    deadlines = app.state.database.deadlines(user)
    assert len(deadlines) == 1 and deadlines[0]["completed"] == 1
    assert deadlines[0]["id"] != 999
    assert app.state.database.deadlines(other)[0]["title"] == "private"
    assert confirm(client, raw, identifier).status_code == 409


def test_preview_rejects_private_fields_malformed_duplicates_and_overlaps(setup):
    app, client, session = setup
    original = client.get("/api/export").content
    for mutation in (lambda d: d.update(user_id="evil"), lambda d: d["preferences"].update(user_id="evil"),
                     lambda d: d.update(schema_version=999), lambda d: d["lessons"].append(d["lessons"][0])):
        document = json.loads(original)
        mutation(document)
        assert preview(client, json.dumps(document).encode()).status_code == 422
    for bad in (b'{"schema_version":1,"schema_version":1}', b"[", b"x" * (5 * 1024 * 1024 + 1)):
        assert preview(client, bad).status_code == 422
    assert json.loads(client.get("/api/export").content)["lessons"] == json.loads(original)["lessons"]


def test_changed_data_file_and_foreign_preview_fail_closed(setup):
    app, client, session = setup
    raw = client.get("/api/export").content
    identifier = preview(client, raw).json()["preview_id"]
    assert confirm(client, raw + b" ", identifier).status_code == 409
    app.state.database.add_deadline(session["user"]["id"], "new", "", "2026-01-01T12:00", "", "manual")
    assert confirm(client, raw, identifier).status_code == 409
    identifier = preview(client, raw).json()["preview_id"]
    other = app.state.database.create_user("Other")["id"]
    issued = app.state.sessions.issue(other)
    client.cookies.set(SESSION_COOKIE, issued.token, domain="testserver.local", path="/")
    client.headers["X-CSRF-Token"] = issued.csrf_token
    assert confirm(client, raw, identifier).status_code == 409
    client.headers.pop("X-CSRF-Token")
    assert preview(client, raw).status_code == 403


def test_database_failure_rolls_back_all_replacement(setup):
    import sqlite3
    app, client, session = setup
    user = session["user"]["id"]
    raw = client.get("/api/export").content
    document = json.loads(raw)
    document["deadlines"] = [{"title": "new", "due_at": "2026-01-01T12:00", "completed": 0}]
    replacement = json.dumps(document).encode()
    identifier = preview(client, replacement).json()["preview_id"]
    with app.state.database.connection() as db:
        db.execute("CREATE TRIGGER fail_restore BEFORE INSERT ON deadlines BEGIN SELECT RAISE(ABORT,'synthetic disk failure'); END")
    with pytest.raises(sqlite3.DatabaseError):
        app.state.restore.confirm(user, replacement, identifier)
    assert json.loads(client.get("/api/export").content)["lessons"] == json.loads(raw)["lessons"]
