from datetime import datetime

from sqlmodel import Field, SQLModel

from app.auth.models import utcnow


class HomeLayout(SQLModel, table=True):
    """How one person arranged their home screen: the JSON of a Layout, kept as text."""

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    data: str
    updated_at: datetime = Field(default_factory=utcnow)
