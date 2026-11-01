from datetime import date, datetime

from sqlmodel import Field, SQLModel

from app.auth.models import utcnow


class TradingLevel(SQLModel, table=True):
    """A price level typed in by hand from an analysis: where to look for a trade, and its stop."""

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    # One of the instrument names on the settings page, e.g. "DAX".
    instrument: str = Field(max_length=20, index=True)
    # "long" or "short".
    bias: str = Field(max_length=5)
    # The entry zone; a single level has entry_low == entry_high.
    entry_low: float
    entry_high: float
    stop: float
    # Free text, e.g. "25400, 25200".
    targets: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=300)
    # The watcher ignores the level after this day (in the hub's timezone).
    valid_until: date | None = None
    active: bool = True
    last_alert_at: datetime | None = None


class TradingAlert(SQLModel, table=True):
    """Every alert the watcher sent (or tried to send), newest kept for a year."""

    id: int | None = Field(default=None, primary_key=True)
    at: datetime = Field(default_factory=utcnow, index=True)
    # "level": price came near a level. "post": a new analysis was posted. "test": by hand.
    kind: str = Field(max_length=8)
    # Not a foreign key, so deleting a level keeps its alerts.
    level_id: int | None = None
    instrument: str = Field(default="", max_length=20)
    price: float | None = None
    title: str = Field(default="", max_length=100)
    message: str = Field(default="", max_length=500)
    link: str = Field(default="", max_length=300)
    delivered: bool = False
    error: str = Field(default="", max_length=200)
