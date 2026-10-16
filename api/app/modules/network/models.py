from datetime import datetime

from sqlmodel import Field, SQLModel

from app.auth.models import utcnow


class NetworkDevice(SQLModel, table=True):
    """A device the Pi has seen on the home network, by MAC address."""

    mac: str = Field(primary_key=True, max_length=17)
    ip: str = Field(default="", max_length=64)
    # What the router's DNS calls it, from the latest scan.
    hostname: str = Field(default="", max_length=64)
    # A name an admin gave it, e.g. "Living room TV".
    name: str = Field(default="", max_length=64)
    first_seen: datetime = Field(default_factory=utcnow)
    last_seen: datetime = Field(default_factory=utcnow)
    # False until an admin says they recognise it: that's what makes a new-device alert.
    known: bool = False
    is_pi: bool = False


class InternetHour(SQLModel, table=True):
    """The once-a-minute internet checks, added up per hour so the Pi writes little."""

    hour: datetime = Field(primary_key=True)
    checks: int = 0
    failures: int = 0
    # Sum of the round trips that succeeded, for the hour's average.
    latency_ms_total: float = 0
    latency_ms_max: float = 0


class Outage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(index=True)
    # None while the connection is still down.
    ended_at: datetime | None = None


class SpeedTest(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    at: datetime = Field(default_factory=utcnow, index=True)
    # "scheduled" or "manual".
    trigger: str = Field(max_length=16)
    ping_ms: float | None = None
    down_mbps: float | None = None
    up_mbps: float | None = None
    error: str = Field(default="", max_length=200)
