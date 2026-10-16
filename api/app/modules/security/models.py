from datetime import date, datetime

from sqlmodel import Field, SQLModel, UniqueConstraint

from app.auth.models import utcnow


class HubSetting(SQLModel, table=True):
    """Settings an admin changes from the hub itself, as opposed to HUB_* environment variables."""

    key: str = Field(primary_key=True, max_length=64)
    value: str = ""
    changed_at: datetime = Field(default_factory=utcnow)
    changed_by: int | None = Field(default=None, foreign_key="user.id")


class AccessAttempt(SQLModel, table=True):
    """Refused requests, failed logins and away visits, counted per address per day."""

    __table_args__ = (UniqueConstraint("kind", "ip", "day"),)

    id: int | None = Field(default=None, primary_key=True)
    # "blocked": refused by the network gate. "login": wrong password. "away": let in over the VPN.
    kind: str = Field(index=True, max_length=16)
    ip: str = Field(max_length=64)
    day: date = Field(index=True)
    count: int = 0
    # The last path requested, or the username tried for a failed login.
    detail: str = Field(default="", max_length=200)
    last_seen: datetime = Field(default_factory=utcnow)


class SecurityReport(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=utcnow, index=True)
    finished_at: datetime | None = None
    # "scheduled" or "manual".
    trigger: str = Field(max_length=16)
    status: str = Field(default="unknown", max_length=16)
    # The checks, as a JSON list of app.modules.security.checks.Check.
    checks: str = "[]"
