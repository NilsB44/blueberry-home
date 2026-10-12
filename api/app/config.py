from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HUB_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/hub.db"
    # Session cookies are only sent over HTTPS when true. Caddy serves HTTPS on the Pi,
    # so keep this on in production and off for plain-HTTP local development.
    cookie_secure: bool = True
    session_days: int = 30
    ollama_url: str = "http://ollama:11434"
    assistant_model: str = "qwen3:4b"
    content_dir: Path = Path(__file__).resolve().parent.parent / "content"
    # Streaks and "today" are counted in this timezone.
    timezone: str = "Europe/Stockholm"
    daily_xp_goal: int = 30
    # The Rust equity engine. In Docker it's on PATH; in development, build it with
    # `cargo build --release` in engines/poker and it's found there.
    poker_engine: str = "poker-engine"
    # Shared files (shared/ and home/<user id>/). Put this on the SSD on the Pi.
    files_dir: Path = Path("./data/files")
    max_upload_mb: int = 8192


@lru_cache
def get_settings() -> Settings:
    return Settings()
