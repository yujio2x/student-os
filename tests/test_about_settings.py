from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def bootstrap(app, mode: str = "guest") -> dict:
    with TestClient(app) as client:
        response = client.post(f"/api/auth/{mode}")
        assert response.status_code == 200
        return client.get("/api/bootstrap").json()


def test_about_is_public_to_guest_and_normal_user(tmp_path: Path) -> None:
    settings = Settings(tmp_path / "about.db", "", "demo")
    guest = bootstrap(create_app(settings))
    user = bootstrap(create_app(settings), "dev-login")

    for payload in (guest, user):
        assert payload["project"] == {
            "name": "Student OS",
            "version": "v0.1 Beta",
            "description": "Student OS — приложение для студентов с расписанием, дедлайнами, календарём и Student AI.",
            "github_url": "https://github.com/yujio2x/student-os",
            "telegram_url": "",
            "support_email": "",
        }


def test_optional_about_contacts_are_validated(tmp_path: Path) -> None:
    valid = Settings(
        tmp_path / "valid.db", "", "demo",
        project_telegram_url="https://t.me/student_os",
        support_email="support@example.kz",
    )
    project = bootstrap(create_app(valid))["project"]
    assert project["telegram_url"] == "https://t.me/student_os"
    assert project["support_email"] == "support@example.kz"

    invalid = Settings(
        tmp_path / "invalid.db", "", "demo",
        project_github_url="javascript:alert(1)",
        project_telegram_url="https://example.com/not-a-telegram-channel",
        support_email="not-an-email",
    )
    project = bootstrap(create_app(invalid))["project"]
    assert project["github_url"] == ""
    assert project["telegram_url"] == ""
    assert project["support_email"] == ""


def test_about_section_has_no_auth_or_admin_rendering_dependency(tmp_path: Path) -> None:
    app = create_app(Settings(tmp_path / "shell.db", "", "demo"))
    with TestClient(app) as client:
        html = client.get("/").text
    assert 'id="aboutSettings"' in html
    assert "О проекте" in html
    assert 'id="aboutGithub"' in html
    assert 'href=""' not in html
