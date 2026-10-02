"""Environment-based application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_path(value: str, default: Path) -> Path:
    path = Path(value).expanduser() if value else default
    return path if path.is_absolute() else BASE_DIR / path


@dataclass(frozen=True)
class Settings:
    youtube_api_key: str
    gemini_api_key: str
    gemini_model: str
    client_secrets_file: Path
    oauth_local_port: int
    enable_auto_moderation: bool
    data_dir: Path
    flask_host: str
    flask_port: int
    flask_debug: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", "").strip(),
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip(),
            client_secrets_file=_resolve_path(
                os.getenv("GOOGLE_CLIENT_SECRETS_FILE", ""),
                BASE_DIR / "secrets" / "client_secret.json",
            ),
            oauth_local_port=int(os.getenv("OAUTH_LOCAL_PORT", "8080")),
            enable_auto_moderation=_as_bool(
                os.getenv("ENABLE_AUTO_MODERATION"), default=False
            ),
            data_dir=_resolve_path(
                os.getenv("DATA_DIR", ""), BASE_DIR / "data" / "runtime"
            ),
            flask_host=os.getenv("FLASK_HOST", "127.0.0.1"),
            flask_port=int(os.getenv("FLASK_PORT", "5000")),
            flask_debug=_as_bool(os.getenv("FLASK_DEBUG"), default=False),
        )

    def missing_dashboard_config(self) -> list[str]:
        return [] if self.youtube_api_key else ["YOUTUBE_API_KEY"]

    def validate_pipeline(self, moderate: bool = False) -> None:
        missing = []
        if not self.youtube_api_key:
            missing.append("YOUTUBE_API_KEY")
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if moderate and not self.client_secrets_file.is_file():
            missing.append("GOOGLE_CLIENT_SECRETS_FILE")
        if missing:
            raise RuntimeError(
                "Konfigurasi belum lengkap: " + ", ".join(missing) + ". Lihat .env.example."
            )
