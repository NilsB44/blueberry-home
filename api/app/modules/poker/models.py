from datetime import datetime

from sqlmodel import Field, SQLModel, UniqueConstraint

from app.auth.models import utcnow


class PokerGame(SQLModel, table=True):
    __tablename__ = "poker_game"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=80)
    currency: str = Field(default="SEK", max_length=3)
    default_buy_in: int = 0  # minor units
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
    settled_at: datetime | None = None


class PokerEntry(SQLModel, table=True):
    """One player's buy-ins and final stack in one game."""

    __tablename__ = "poker_entry"
    __table_args__ = (UniqueConstraint("game_id", "player"),)

    id: int | None = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="poker_game.id", index=True)
    player: str = Field(max_length=40)
    buy_in: int = 0  # total paid in, minor units
    buy_ins: int = 0  # number of buy-ins, rebuys included
    cash_out: int | None = None
