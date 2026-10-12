from datetime import UTC, datetime, timedelta

from fsrs import Card, Rating, Scheduler

from app.modules.learn.grading import Verdict

# One short learning step: a word met in a lesson comes back the next day or so,
# and a forgotten one comes back ten minutes later in the same session.
scheduler = Scheduler(
    desired_retention=0.9,
    learning_steps=(timedelta(minutes=10),),
    relearning_steps=(timedelta(minutes=10),),
)

RATING_FOR: dict[Verdict, Rating] = {
    "correct": Rating.Good,
    "accent": Rating.Hard,
    "typo": Rating.Hard,
    "wrong": Rating.Again,
}


def new_card(now: datetime | None = None) -> Card:
    return Card(due=now or datetime.now(UTC))


def review(card_json: str, rating: Rating, now: datetime | None = None) -> Card:
    card = Card.from_json(card_json)
    updated, _log = scheduler.review_card(card, rating, review_datetime=now or datetime.now(UTC))
    return updated
