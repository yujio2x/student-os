from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_path: Path
    openai_api_key: str
    openai_model: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        database_path=Path(os.getenv("DATABASE_PATH", "data/student_os.db")),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip(),
    )

