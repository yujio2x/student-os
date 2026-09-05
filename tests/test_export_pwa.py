from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.export_service import OwnedDataExportService
from app.main import create_app


def login(client: TestClient) -> dict:
    session = client.post("/api/auth/dev-login").json()
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    return session


def test_export_is_authenticated_owned_versioned_and_secret_free(tmp_path: Path) -> None:
    app = create_app(Settings(tmp_path / "export.db", "super-secret-key", "gpt-5.6-luna"))
    with TestClient(app) as client:
        assert client.get("/api/export").status_code == 401
        owner = login(client)
        created = client.post(
            "/api/deadlines",
            json={"title": "Қазақша дедлайн", "due_at": "2026-10-01T12:00", "source": "manual"},
        ).json()
        outsider = app.state.database.create_user("Другой пользователь")
        app.state.database.add_deadline(
            outsider["id"], "Чужой секрет", "", "2026-11-01T12:00", "private", "manual"
        )

        response = client.get("/api/export")

        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="student-os-export.json"'
        data = response.json()
        assert data["schema_version"] == 1
        assert data["exported_at"].endswith("+00:00")
        assert [item["id"] for item in data["deadlines"]] == [created["id"]]
        assert data["deadlines"][0]["title"] == "Қазақша дедлайн"
        assert data["preferences"]["theme"] == "light"
        rendered = response.text
        for forbidden in (
            "user_id", "csrf", "session", "telegram", "super-secret-key", "Чужой секрет"
        ):
            assert forbidden not in rendered
        assert owner["user"]["id"] not in rendered


def test_export_rejects_record_and_size_overflow(tmp_path: Path) -> None:
    app = create_app(Settings(tmp_path / "bounded.db", "", "gpt-5.6-luna"))
    with TestClient(app) as client:
        login(client)
        app.state.owned_export = OwnedDataExportService(app.state.database, max_records=1)
        assert client.get("/api/export").status_code == 413

        app.state.owned_export = OwnedDataExportService(app.state.database, max_bytes=10)
        assert client.get("/api/export").status_code == 413


def test_pwa_manifest_and_worker_keep_authenticated_data_out_of_cache(tmp_path: Path) -> None:
    app = create_app(Settings(tmp_path / "pwa.db", "", "gpt-5.6-luna"))
    with TestClient(app) as client:
        manifest_response = client.get("/static/manifest.webmanifest")
        response = client.get("/sw.js")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
        assert "javascript" in response.headers["content-type"]
        worker = response.text
        html = client.get("/").text

    manifest = json.loads(manifest_response.text)
    assert manifest_response.status_code == 200
    assert manifest["name"] == "Student OS"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512", "any"}
    assert manifest["theme_color"] == "#17171b"
    assert 'rel="manifest"' in html
    assert 'rel="apple-touch-icon"' in html
    app_js = (Path(__file__).parents[1] / "static" / "pwa.js").read_text(encoding="utf-8")
    assert "serviceWorker.register" in app_js
    assert 'register("/sw.js",{scope:"/"})' in app_js
    assert "beforeinstallprompt" in app_js
    assert "appinstalled" in app_js
    assert "/static/pwa.js" in html
    assert html.index('/static/theme.js') < html.index('/static/styles.css')
    assert "/static/theme.js" in worker
    assert 'url.pathname.startsWith("/api/")' in worker
    assert 'url.pathname.startsWith("/admin")' in worker
    assert "PUBLIC_SHELL.includes(url.pathname)" in worker
    assert "/api/" not in " ".join(worker.split("PUBLIC_SHELL=")[1].split(";")[0:1])
    for name in ("icon-192.png", "icon-512.png"):
        icon = (Path(__file__).parents[1] / "static" / name).read_bytes()
        assert icon.startswith(b"\x89PNG\r\n\x1a\n")
