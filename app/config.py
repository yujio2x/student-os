from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


APP_NAME = "Student OS"
APP_VERSION = "0.1.0"
APP_VERSION_LABEL = f"v{APP_VERSION.removesuffix('.0')} Beta"
APP_DESCRIPTION = (
    "Student OS — приложение для студентов с расписанием, дедлайнами, "
    "календарём и Student AI."
)
DEFAULT_PROJECT_GITHUB_URL = "https://github.com/yujio2x/student-os"


def valid_public_url(value: str, allowed_hosts: frozenset[str]) -> str:
    value = value.strip()
    if any(character.isspace() or character == "\\" for character in value):
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.hostname.lower() not in allowed_hosts
    ):
        return ""
    return value


def valid_support_email(value: str) -> str:
    value = value.strip()
    if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        return ""
    return value


@dataclass(frozen=True)
class Settings:
    database_path: Path
    openai_api_key: str
    openai_model: str
    environment: str = "development"
    session_ttl_hours: int = 168
    secure_cookies: bool = False
    dev_login_enabled: bool = True
    telegram_bot_token: str = ""
    telegram_auth_max_age_seconds: int = 300
    owner_telegram_id: str = ""
    entitlement_source: str = "core"
    dev_admin_enabled: bool = False
    bot_bridge_secret: str = ""
    bot_bridge_max_age_seconds: int = 300
    telegram_bot_username: str = ""
    telegram_client_id: str = ""
    telegram_client_secret: str = ""
    telegram_redirect_uri: str = ""
    database_url: str = field(default="", repr=False)
    project_github_url: str = DEFAULT_PROJECT_GITHUB_URL
    project_telegram_url: str = ""
    support_email: str = ""


def project_metadata(settings: Settings) -> dict[str, str]:
    return {
        "name": APP_NAME,
        "version": APP_VERSION_LABEL,
        "description": APP_DESCRIPTION,
        "github_url": valid_public_url(
            settings.project_github_url, frozenset({"github.com", "www.github.com"})
        ),
        "telegram_url": valid_public_url(
            settings.project_telegram_url,
            frozenset({"t.me", "telegram.me", "www.telegram.me"}),
        ),
        "support_email": valid_support_email(settings.support_email),
    }


def load_settings() -> Settings:
    load_dotenv()
    environment = os.getenv("APP_ENV", "production" if os.getenv("DYNO") else "development").strip().lower()
    if environment in {"production", "staging"} and not os.getenv("DATABASE_URL", "").strip():
        raise RuntimeError("Cloud requires PostgreSQL DATABASE_URL; SQLite is local-only")
    return Settings(
        database_path=Path(os.getenv("DATABASE_PATH", "data/student_os.db")),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip(),
        environment=environment,
        session_ttl_hours=max(1, int(os.getenv("SESSION_TTL_HOURS", "168"))),
        secure_cookies=environment in {"production", "staging"},
        dev_login_enabled=environment == "development" and os.getenv("DEV_LOGIN_ENABLED", "false").strip().lower() == "true",
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_auth_max_age_seconds=max(
            60, int(os.getenv("TELEGRAM_AUTH_MAX_AGE_SECONDS", "300"))
        ),
        owner_telegram_id=os.getenv("OWNER_TELEGRAM_ID", "").strip(),
        entitlement_source=os.getenv("ENTITLEMENT_SOURCE", "core").strip().lower(),
        dev_admin_enabled=(
            environment == "development"
            and os.getenv("DEV_ADMIN_ENABLED", "false").strip().lower() == "true"
        ),
        bot_bridge_secret=os.getenv("BOT_BRIDGE_SECRET", "").strip(),
        bot_bridge_max_age_seconds=max(
            30, int(os.getenv("BOT_BRIDGE_MAX_AGE_SECONDS", "300"))
        ),
        telegram_bot_username=os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@"),
        telegram_client_id=os.getenv("TELEGRAM_CLIENT_ID", "").strip(),
        telegram_client_secret=os.getenv("TELEGRAM_CLIENT_SECRET", "").strip(),
        telegram_redirect_uri=os.getenv("TELEGRAM_REDIRECT_URI", "").strip(),
        database_url=os.getenv("DATABASE_URL", "").strip(),
        project_github_url=os.getenv(
            "PROJECT_GITHUB_URL", DEFAULT_PROJECT_GITHUB_URL
        ).strip(),
        project_telegram_url=os.getenv("PROJECT_TELEGRAM_URL", "").strip(),
        support_email=os.getenv("SUPPORT_EMAIL", "").strip(),
    )
