"""Language courses (French, Mandarin): lessons, answer checking, XP and reviews."""

import random
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import col, func, select

from app.auth.deps import CurrentUser, DbSession
from app.config import get_settings
from app.modules.learn.content import (
    Course,
    CourseMeta,
    Exercise,
    Gap,
    Match,
    Write,
    accepted_answers,
    accepted_readings,
    answer_lang,
    get_course,
    pinyin_dict,
    public_exercise,
)
from app.modules.learn.grading import Result, Verdict, grade, grade_chinese, normalize
from app.modules.learn.models import LessonProgress, SrsCard, XpEvent
from app.modules.learn.srs import RATING_FOR, new_card, review

router = APIRouter(prefix="/api/learn/{course_id}", tags=["learn"])

LESSON_XP = 10
PERFECT_BONUS_XP = 5
REVIEW_XP = 1


def course_dep(course_id: str) -> Course:
    if not course_id.isalnum() or not (get_settings().content_dir / course_id).is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such course")
    return get_course(course_id)


CourseDep = Annotated[Course, Depends(course_dep)]


def local_today() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def alternatives(text: str) -> list[str]:
    return [t.strip() for t in text.split(" / ") if t.strip()]


# ---------- schemas ----------


class LessonSummary(BaseModel):
    id: str
    title: str
    exercises: int
    completed: bool
    best_mistakes: int | None


class UnitOut(BaseModel):
    id: str
    title: str
    description: str
    cefr: str
    lessons: list[LessonSummary]


class CourseOut(BaseModel):
    id: str
    meta: CourseMeta
    units: list[UnitOut]
    next_lesson: str | None
    # Chinese only: reading for each word and character the course shows.
    pinyin: dict[str, str] = {}


class Stats(BaseModel):
    xp_today: int
    daily_goal: int
    streak: int
    total_xp: int
    due: int
    words: int


class CheckIn(BaseModel):
    index: int = Field(ge=0)
    answer: str = Field(max_length=500)


class CheckOut(BaseModel):
    verdict: Verdict
    correct: bool
    expected: str


class CompleteIn(BaseModel):
    mistakes: int = Field(ge=0, le=100)


class CompleteOut(BaseModel):
    xp: int
    new_words: int
    stats: Stats


ReviewMode = Literal["to_en", "from_en", "listen"]


class ReviewItem(BaseModel):
    id: int
    mode: ReviewMode
    prompt: str
    reading: str | None = None


class ReviewIn(BaseModel):
    mode: ReviewMode
    answer: str = Field(max_length=500)


class ReviewOut(CheckOut):
    next_due: datetime


# ---------- helpers ----------


def _stats(db: DbSession, user_id: int, course: Course) -> Stats:
    today = local_today()
    events = db.exec(
        select(XpEvent.day, func.sum(XpEvent.xp))
        .where(XpEvent.user_id == user_id)
        .group_by(XpEvent.day)
    ).all()
    by_day = {d: xp for d, xp in events}
    streak = 0
    day = today if today in by_day else today - timedelta(days=1)
    while day in by_day:
        streak += 1
        day -= timedelta(days=1)
    course_xp = db.exec(
        select(func.coalesce(func.sum(XpEvent.xp), 0)).where(
            XpEvent.user_id == user_id, XpEvent.course == course.id
        )
    ).one()
    cards = (
        select(func.count())
        .select_from(SrsCard)
        .where(SrsCard.user_id == user_id, SrsCard.course == course.id)
    )
    due = db.exec(cards.where(SrsCard.due <= datetime.now(UTC))).one()
    words = db.exec(cards).one()
    return Stats(
        xp_today=by_day.get(today, 0),
        daily_goal=get_settings().daily_xp_goal,
        streak=streak,
        total_xp=course_xp,
        due=due,
        words=words,
    )


def grade_target(course: Course, answer: str, accepted: list[str], readings: list[str]) -> Result:
    """Grade an answer written in the language being learned."""
    if course.meta.is_chinese:
        return grade_chinese(answer, accepted, readings)
    return grade(answer, accepted, "fr")


def _check(course: Course, ex: Exercise, answer: str) -> Result:
    if isinstance(ex, Match | Write):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{ex.type} exercises are checked locally")
    accepted = accepted_answers(ex)
    if isinstance(ex, Gap) and ex.options:
        # Tapped from a fixed list: no partial credit.
        ok = normalize(answer) == normalize(accepted[0])
        return Result("correct" if ok else "wrong", accepted[0])
    if ex.type == "choice":
        ok = answer == accepted[0]
        return Result("correct" if ok else "wrong", accepted[0])
    if answer_lang(ex) == "en":
        return grade(answer, accepted, "en")
    return grade_target(course, answer, accepted, accepted_readings(ex))


# ---------- routes ----------


@router.get("/course")
def course_overview(course: CourseDep, user: CurrentUser, db: DbSession) -> CourseOut:
    progress = {
        p.lesson_id: p
        for p in db.exec(
            select(LessonProgress).where(
                LessonProgress.user_id == user.id, LessonProgress.course == course.id
            )
        )
    }
    units = [
        UnitOut(
            id=u.id,
            title=u.title,
            description=u.description,
            cefr=u.cefr,
            lessons=[
                LessonSummary(
                    id=lesson.id,
                    title=lesson.title,
                    exercises=len(lesson.exercises),
                    completed=lesson.id in progress,
                    best_mistakes=progress[lesson.id].best_mistakes
                    if lesson.id in progress
                    else None,
                )
                for lesson in u.lessons
            ],
        )
        for u in course.units
    ]
    next_lesson = next(
        (lesson.id for lesson in course.lessons() if lesson.id not in progress), None
    )
    return CourseOut(
        id=course.id,
        meta=course.meta,
        units=units,
        next_lesson=next_lesson,
        pinyin=pinyin_dict(course.id),
    )


@router.get("/stats")
def stats(course: CourseDep, user: CurrentUser, db: DbSession) -> Stats:
    return _stats(db, user.id, course)


@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: str, course: CourseDep, _: CurrentUser) -> dict:
    lesson = course.lesson(lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such lesson")
    rng = random.Random()
    return {
        "id": lesson.id,
        "title": lesson.title,
        "intro": lesson.intro,
        "vocab": [v.model_dump() for v in lesson.vocab],
        "exercises": [public_exercise(ex, rng) for ex in lesson.exercises],
    }


@router.get("/strokes/{char}")
def strokes(char: str, course: CourseDep, _: CurrentUser) -> FileResponse:
    """Stroke-order data for the character-writing exercise (vendored, works offline)."""
    if len(char) != 1 or not "\u4e00" <= char <= "\u9fff":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No stroke data")
    path = get_settings().content_dir / course.id / "strokes" / f"{char}.json"
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No stroke data")
    return FileResponse(
        path, media_type="application/json", headers={"Cache-Control": "max-age=86400"}
    )


@router.post("/lessons/{lesson_id}/check")
def check(lesson_id: str, body: CheckIn, course: CourseDep, _: CurrentUser) -> CheckOut:
    lesson = course.lesson(lesson_id)
    if lesson is None or body.index >= len(lesson.exercises):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such exercise")
    result = _check(course, lesson.exercises[body.index], body.answer)
    return CheckOut(verdict=result.verdict, correct=result.correct, expected=result.expected)


@router.post("/lessons/{lesson_id}/complete")
def complete(
    lesson_id: str, body: CompleteIn, course: CourseDep, user: CurrentUser, db: DbSession
) -> CompleteOut:
    lesson = course.lesson(lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such lesson")

    progress = db.exec(
        select(LessonProgress).where(
            LessonProgress.user_id == user.id,
            LessonProgress.course == course.id,
            LessonProgress.lesson_id == lesson.id,
        )
    ).first() or LessonProgress(user_id=user.id, course=course.id, lesson_id=lesson.id)
    progress.times_completed += 1
    if progress.best_mistakes is None or body.mistakes < progress.best_mistakes:
        progress.best_mistakes = body.mistakes
    progress.last_completed_at = datetime.now(UTC)
    db.add(progress)

    xp = LESSON_XP + (PERFECT_BONUS_XP if body.mistakes == 0 else 0)
    db.add(
        XpEvent(
            user_id=user.id,
            course=course.id,
            day=local_today(),
            xp=xp,
            source=f"lesson:{lesson.id}",
        )
    )

    existing = set(
        db.exec(
            select(SrsCard.front).where(
                SrsCard.user_id == user.id,
                SrsCard.course == course.id,
                col(SrsCard.front).in_([v.word for v in lesson.vocab]),
            )
        )
    )
    new_words = 0
    for v in lesson.vocab:
        if v.word in existing:
            continue
        # Meeting a word in a lesson counts as a first successful review.
        card = review(new_card().to_json(), RATING_FOR["correct"])
        db.add(
            SrsCard(
                user_id=user.id,
                course=course.id,
                front=v.word,
                reading=v.reading,
                back=v.en,
                lesson_id=lesson.id,
                due=card.due,
                reps=1,
                fsrs=card.to_json(),
            )
        )
        new_words += 1
    db.commit()
    return CompleteOut(xp=xp, new_words=new_words, stats=_stats(db, user.id, course))


def _mode_for(card: SrsCard) -> ReviewMode:
    # Recognition first, then production, then listening, then repeat.
    return ("to_en", "from_en", "listen")[(card.reps - 1) % 3]


@router.get("/review")
def review_queue(
    course: CourseDep,
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
) -> list[ReviewItem]:
    cards = db.exec(
        select(SrsCard)
        .where(
            SrsCard.user_id == user.id,
            SrsCard.course == course.id,
            SrsCard.due <= datetime.now(UTC),
        )
        .order_by(SrsCard.due)
        .limit(limit)
    ).all()
    items = []
    for c in cards:
        mode = _mode_for(c)
        prompt = c.back if mode == "from_en" else c.front
        reading = c.reading if mode == "to_en" else None
        items.append(ReviewItem(id=c.id, mode=mode, prompt=prompt, reading=reading))
    return items


@router.post("/review/{card_id}")
def answer_review(
    card_id: int, body: ReviewIn, course: CourseDep, user: CurrentUser, db: DbSession
) -> ReviewOut:
    card = db.get(SrsCard, card_id)
    if card is None or card.user_id != user.id or card.course != course.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such card")
    if body.mode == "to_en":
        result = grade(body.answer, alternatives(card.back), "en")
    else:
        readings = alternatives(card.reading or "")
        result = grade_target(course, body.answer, alternatives(card.front), readings)

    updated = review(card.fsrs, RATING_FOR[result.verdict])
    card.fsrs = updated.to_json()
    card.due = updated.due
    card.reps += 1
    if not result.correct:
        card.lapses += 1
    db.add(card)
    if result.correct:
        db.add(
            XpEvent(
                user_id=user.id, course=course.id, day=local_today(), xp=REVIEW_XP, source="review"
            )
        )
    db.commit()
    return ReviewOut(
        verdict=result.verdict,
        correct=result.correct,
        expected=result.expected,
        next_due=updated.due,
    )
