"""集中配置：路径与可覆盖项，避免散落在各模块。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_db_url() -> str:
    db_path = (PROJECT_ROOT / "data" / "stagemind.db").as_posix()
    return os.environ.get("STAGEMIND_DB_URL", f"sqlite:///{db_path}")


@dataclass(frozen=True)
class Settings:
    app_name: str = "StageMind"
    data_dir: Path = PROJECT_ROOT / "data"
    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"
    frontend_dir: Path = PROJECT_ROOT / "frontend"
    database_url: str = field(default_factory=_default_db_url)
    cors_origins: tuple[str, ...] = ("*",)
    reminder_webhook_url: str = os.environ.get("STAGEMIND_WEBHOOK_URL", "")

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
