from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
