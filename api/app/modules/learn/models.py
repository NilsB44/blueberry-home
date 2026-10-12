from datetime import date, datetime

from sqlmodel import Field, SQLModel, UniqueConstraint

from app.auth.models import utcnow


class LessonProgress(SQLModel, table=True):
    __tablename__ = "lang_lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "course", "lesson_id"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    course: str
    lesson_id: str
    times_completed: int = 0
    best_mistakes: int | None = None
    last_completed_at: datetime = Field(default_factory=utcnow)


class SrsCard(SQLModel, table=True):
    """One word or phrase the learner has met, scheduled with FSRS."""

    __tablename__ = "lang_srs_card"
    __table_args__ = (UniqueConstraint("user_id", "course", "front"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    course: str
    front: str  # target language (French)
    back: str  # English, alternatives separated by " / "
    lesson_id: str
    due: datetime = Field(index=True)
    reps: int = 0
    lapses: int = 0
    fsrs: str  # fsrs.Card serialised as JSON


class XpEvent(SQLModel, table=True):
    __tablename__ = "lang_xp_event"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    course: str
    day: date = Field(index=True)  # local day, see Settings.timezone
    xp: int
    source: str  # "lesson:<id>" or "review"
    created_at: datetime = Field(default_factory=utcnow)
