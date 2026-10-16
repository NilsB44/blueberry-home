from datetime import datetime

from sqlmodel import Field, SQLModel

from app.auth.models import utcnow


class TetrisScore(SQLModel, table=True):
    """A finished solo game, for the high-score table."""

    __tablename__ = "tetris_score"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    score: int = Field(index=True)
    lines: int = 0
    level: int = 1
    created_at: datetime = Field(default_factory=utcnow)
