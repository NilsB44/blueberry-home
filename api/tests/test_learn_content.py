"""Every shipped lesson must load and be answerable; this catches content typos in CI."""

import random

import pytest

from app.config import get_settings
from app.modules.learn.content import (
    Gap,
    Match,
    WordBank,
    Write,
    accepted_answers,
    accepted_readings,
    get_course,
    public_exercise,
)
from app.modules.learn.router import _check

COURSES = sorted(
    p.name for p in get_settings().content_dir.iterdir() if (p / "course.yaml").is_file()
)
LESSONS = [
    (course_id, lesson) for course_id in COURSES for lesson in get_course(course_id).lessons()
]


def lesson_id(item):
    return f"{item[0]}:{item[1].id}" if isinstance(item, tuple) else None


def test_courses_are_found():
    assert {"french", "mandarin"} <= set(COURSES)


@pytest.mark.parametrize("course_id", COURSES)
def test_course_has_lessons(course_id):
    assert len(get_course(course_id).lessons()) >= 4


@pytest.mark.parametrize("item", LESSONS, ids=lesson_id)
def test_every_exercise_accepts_its_own_answers(item):
    course_id, lesson = item
    course = get_course(course_id)
    for ex in lesson.exercises:
        if isinstance(ex, Match | Write):
            continue
        # A gap with options is filled by tapping, so only the characters can arrive.
        tapped = isinstance(ex, Gap) and ex.options
        readings = [] if tapped else accepted_readings(ex)
        for answer in accepted_answers(ex) + readings:
            assert _check(course, ex, answer).verdict == "correct", (ex, answer)


@pytest.mark.parametrize("item", LESSONS, ids=lesson_id)
def test_word_bank_tiles_can_build_the_answer(item):
    for ex in item[1].exercises:
        if isinstance(ex, WordBank):
            tiles = public_exercise(ex, random.Random(0))["tiles"]
            for d in ex.distractors:
                tiles.remove(d)
            words = [w.strip(".,!?，。？！") for w in ex.answer.split()]
            assert sorted(tiles) == sorted(w for w in words if w)


@pytest.mark.parametrize("item", LESSONS, ids=lesson_id)
def test_public_view_hides_answers(item):
    for ex in item[1].exercises:
        view = public_exercise(ex, random.Random(0))
        assert not {"answer", "answers", "also", "readings"} & set(view)


@pytest.mark.parametrize("course_id", COURSES)
def test_vocab_is_unique_per_course(course_id):
    fronts = [v.word for lesson in get_course(course_id).lessons() for v in lesson.vocab]
    assert len(fronts) == len(set(fronts))


def test_chinese_vocab_has_pinyin():
    for lesson in get_course("mandarin").lessons():
        for v in lesson.vocab:
            assert v.reading, v.word


def test_write_exercises_have_stroke_data():
    strokes = get_settings().content_dir / "mandarin" / "strokes"
    for lesson in get_course("mandarin").lessons():
        for ex in lesson.exercises:
            if isinstance(ex, Write):
                assert (strokes / f"{ex.char}.json").is_file(), ex.char
