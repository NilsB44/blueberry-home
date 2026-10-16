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
    # Keep this to home ranges; reaching the hub from outside goes through away_networks.
    trusted_networks: list[str] = [
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    ]
    # Your VPN's addresses (Tailscale's by default). Devices here are only let in while an admin
    # has turned away access on in Security, and only devices that already joined at home.
    away_networks: list[str] = ["100.64.0.0/10", "fd7a:115c:a1e0::/48"]
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
    # The weekly security check runs at this weekday (0 = Monday) and hour, in `timezone`.
    # The Pi's own check (scripts/pi-security-check.py) runs an hour earlier.
    security_schedule: bool = True
    security_check_weekday: int = 6
    security_check_hour: int = 4
    # Written weekly by scripts/pi-security-check.py on the Pi, read into the hub's report.
    host_report_path: Path = Path("./data/host-security.json")
    # Known vulnerabilities in the API's Python packages are looked up here (outbound only).
    osv_url: str = "https://api.osv.dev/v1/querybatch"


@lru_cache
def get_settings() -> Settings:
    return Settings()
