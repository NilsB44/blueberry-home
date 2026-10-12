"""Every shipped lesson must load and be answerable; this catches content typos in CI."""

import random

import pytest

from app.modules.learn.content import (
    Translate,
    WordBank,
    accepted_answers,
    get_course,
    public_exercise,
)
from app.modules.learn.grading import grade

course = get_course("french")
lessons = course.lessons()


def test_course_has_lessons():
    assert len(lessons) >= 5


@pytest.mark.parametrize("lesson", lessons, ids=lambda lesson: lesson.id)
def test_every_exercise_accepts_its_own_answer(lesson):
    for ex in lesson.exercises:
        if ex.type == "match":
            continue
        lang = "en" if isinstance(ex, Translate) and ex.source == "fr" else "fr"
        for answer in accepted_answers(ex):
            assert grade(answer, accepted_answers(ex), lang).verdict == "correct", answer


@pytest.mark.parametrize("lesson", lessons, ids=lambda lesson: lesson.id)
def test_word_bank_tiles_can_build_the_answer(lesson):
    for ex in lesson.exercises:
        if isinstance(ex, WordBank):
            tiles = public_exercise(ex, random.Random(0))["tiles"]
            for d in ex.distractors:
                tiles.remove(d)
            words = [w.strip(".,!?") for w in ex.answer.split()]
            assert sorted(tiles) == sorted(w for w in words if w)


@pytest.mark.parametrize("lesson", lessons, ids=lambda lesson: lesson.id)
def test_public_view_hides_answers(lesson):
    for ex in lesson.exercises:
        view = public_exercise(ex, random.Random(0))
        assert "answer" not in view and "answers" not in view and "also" not in view


def test_vocab_is_unique_per_course():
    fronts = [v.fr for lesson in lessons for v in lesson.vocab]
    assert len(fronts) == len(set(fronts))
