from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


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
    )
