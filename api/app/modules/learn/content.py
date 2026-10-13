"""Course content: lessons are YAML files in api/content/<course>/, one file per unit,
plus a course.yaml describing the language.

Authoring lessons as files keeps them reviewable in git and lets new units ship without
database migrations. Validation happens at load time, so a typo in a lesson fails fast
(and in CI, via tests/test_learn_content.py) instead of in the middle of a lesson.
"""

import random
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from app.config import get_settings


class CourseMeta(BaseModel):
    name: str
    flag: str
    lang: str  # BCP 47 tag used for speech, e.g. fr-FR, zh-CN
    # Shown under answer boxes, e.g. how to type pinyin.
    answer_hint: str | None = None

    @property
    def is_chinese(self) -> bool:
        return self.lang.startswith("zh")


class Vocab(BaseModel):
    word: str  # in the language being learned
    en: str  # alternatives separated by " / "
    reading: str | None = None  # pinyin for Chinese
    note: str | None = None


class Choice(BaseModel):
    type: Literal["choice"]
    prompt: str
    options: list[str] = Field(min_length=2)
    answer: str
    speak: str | None = None  # text in the learned language, read aloud with the prompt

    @model_validator(mode="after")
    def _answer_in_options(self):
        if self.answer not in self.options:
            raise ValueError(f"choice answer {self.answer!r} not in options")
        return self


class Translate(BaseModel):
    type: Literal["translate"]
    prompt: str
    # Language of the prompt: "target" (the language being learned) or "en".
    # The learner answers in the other one.
    source: Literal["target", "en"]
    answers: list[str] = Field(min_length=1)
    prompt_reading: str | None = None  # pinyin shown under a Chinese prompt
    readings: list[str] = []  # pinyin of the answers, accepted instead of characters


class WordBank(BaseModel):
    type: Literal["word_bank"]
    prompt: str
    answer: str
    also: list[str] = []  # other accepted orderings
    distractors: list[str] = []
    readings: list[str] = []


class Match(BaseModel):
    type: Literal["match"]
    pairs: list[tuple[str, str]] = Field(min_length=3, max_length=6)  # (target, en)


class Listen(BaseModel):
    type: Literal["listen"]
    text: str
    also: list[str] = []
    readings: list[str] = []


class Gap(BaseModel):
    type: Literal["gap"]
    prompt: str  # contains "___"
    answers: list[str] = Field(min_length=1)
    hint: str | None = None
    options: list[str] = []  # if given, the gap is filled by tapping instead of typing
    readings: list[str] = []

    @model_validator(mode="after")
    def _has_gap(self):
        if "___" not in self.prompt:
            raise ValueError("gap prompt must contain ___")
        if self.options and self.answers[0] not in self.options:
            raise ValueError("gap answer not in options")
        return self


class Write(BaseModel):
    """Draw a Chinese character stroke by stroke; checked in the browser."""

    type: Literal["write"]
    char: str = Field(min_length=1, max_length=1)
    reading: str
    en: str


Exercise = Annotated[
    Choice | Translate | WordBank | Match | Listen | Gap | Write, Field(discriminator="type")
]


class Lesson(BaseModel):
    id: str
    title: str
    intro: str | None = None
    vocab: list[Vocab] = []
    exercises: list[Exercise] = Field(min_length=1)


class Unit(BaseModel):
    id: str
    order: int
    title: str
    description: str
    cefr: str
    lessons: list[Lesson]


class Course(BaseModel):
    id: str
    meta: CourseMeta
    units: list[Unit]

    def lesson(self, lesson_id: str) -> Lesson | None:
        return next(
            (lesson for u in self.units for lesson in u.lessons if lesson.id == lesson_id), None
        )

    def lessons(self) -> list[Lesson]:
        return [lesson for u in self.units for lesson in u.lessons]


def accepted_readings(ex: Exercise) -> list[str]:
    """Pinyin accepted in place of characters (Chinese courses only)."""
    if isinstance(ex, Translate) and ex.source == "en" or isinstance(ex, WordBank | Listen | Gap):
        return ex.readings
    return []


def answer_lang(ex: Exercise) -> Literal["target", "en"]:
    return "en" if isinstance(ex, Translate) and ex.source == "target" else "target"


def accepted_answers(ex: Exercise) -> list[str]:
    match ex:
        case Choice():
            return [ex.answer]
        case Translate() | Gap():
            return ex.answers
        case WordBank():
            return [ex.answer, *ex.also]
        case Listen():
            return [ex.text, *ex.also]
    raise ValueError(f"{ex.type} is checked on the client")


def public_exercise(ex: Exercise, rng: random.Random) -> dict:
    """What the client sees: no answers, except for match where pairing is the exercise."""
    data = ex.model_dump()
    match ex:
        case Choice():
            data.pop("answer")
            rng.shuffle(data["options"])
        case Translate():
            data.pop("answers")
            data.pop("readings")
        case WordBank():
            # Punctuation isn't part of the puzzle; grading ignores it anyway.
            words = [w.strip(".,!?;:«»，。？！") for w in ex.answer.split()]
            tiles = [w for w in words if w] + ex.distractors
            rng.shuffle(tiles)
            data = {"type": ex.type, "prompt": ex.prompt, "tiles": tiles}
        case Listen():
            data = {"type": ex.type, "text": ex.text}
        case Gap():
            data.pop("answers")
            data.pop("readings")
            rng.shuffle(data["options"])
    return data


def load_course(path: Path) -> Course:
    meta = CourseMeta.model_validate(yaml.safe_load((path / "course.yaml").read_text("utf-8")))
    units = []
    for f in sorted(path.glob("*.yaml")):
        if f.name == "course.yaml":
            continue
        units.append(Unit.model_validate(yaml.safe_load(f.read_text(encoding="utf-8"))))
    units.sort(key=lambda u: u.order)
    ids = [lesson.id for u in units for lesson in u.lessons]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate lesson ids in {path}")
    return Course(id=path.name, meta=meta, units=units)


@lru_cache
def get_course(course_id: str = "french") -> Course:
    return load_course(get_settings().content_dir / course_id)
