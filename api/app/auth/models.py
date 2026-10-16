from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=3, max_length=32)
    display_name: str = Field(max_length=64)
    # Empty for people who joined from a device; only older accounts have a password.
    password_hash: str = ""
    # What the device was when this person joined, e.g. "iPhone" or "Pixel 7".
    device: str | None = Field(default=None, max_length=64)
    is_admin: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class AuthSession(SQLModel, table=True):
    # Only a SHA-256 of the cookie token is stored, so a leaked database can't be used to log in.
    token_hash: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
