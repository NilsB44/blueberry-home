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
    # Devices are remembered by a cookie for this long, so nobody has to log in.
    device_days: int = 3650
    # Anyone on these networks can use the hub without a password: the router is the gate.
    # Add a VPN range here (e.g. Tailscale's 100.64.0.0/10) to reach the hub from outside.
    trusted_networks: list[str] = [
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    ]
    # Name new devices after what the router calls them (reverse DNS), when it says.
    device_names_from_dns: bool = True
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
