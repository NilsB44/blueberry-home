from datetime import datetime

from sqlmodel import Field, SQLModel

from app.auth.models import utcnow


class EconomyData(SQLModel, table=True):
    """The owner's economy page: the JSON of an Economy, kept as text."""

    __tablename__ = "economy_data"

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    data: str
    updated_at: datetime = Field(default_factory=utcnow)
