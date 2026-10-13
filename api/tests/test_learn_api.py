from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app import db as db_module
from app.modules.learn.content import get_course
from app.modules.learn.models import SrsCard

BASE = "/api/learn/french"


def _answers(lesson_id):
    return get_course("french").lesson(lesson_id).exercises


def test_unknown_course_is_404(admin_client):
    assert admin_client.get("/api/learn/klingon/course").status_code == 404
    assert admin_client.get("/api/learn/..%2F..%2Fetc/course").status_code == 404


def test_requires_login(client):
    assert client.get(f"{BASE}/course").status_code == 401


def test_course_overview_starts_at_first_lesson(admin_client):
    body = admin_client.get(f"{BASE}/course").json()
    assert body["next_lesson"] == "salutations"
    assert body["units"][0]["lessons"][0]["completed"] is False


def test_lesson_has_no_answers(admin_client):
    body = admin_client.get(f"{BASE}/lessons/salutations").json()
    assert body["title"] == "Bonjour !"
    assert all("answer" not in ex and "answers" not in ex for ex in body["exercises"])


def test_check_answers(admin_client):
    first = admin_client.post(
        f"{BASE}/lessons/salutations/check", json={"index": 0, "answer": "Bonjour"}
    )
    assert first.json() == {"verdict": "correct", "correct": True, "expected": "Bonjour"}
    wrong = admin_client.post(
        f"{BASE}/lessons/salutations/check", json={"index": 0, "answer": "Merci"}
    )
    assert wrong.json()["correct"] is False
    out_of_range = admin_client.post(
        f"{BASE}/lessons/salutations/check", json={"index": 99, "answer": "x"}
    )
    assert out_of_range.status_code == 404


def test_complete_lesson_awards_xp_and_creates_cards(admin_client):
    resp = admin_client.post(f"{BASE}/lessons/salutations/complete", json={"mistakes": 0})
    body = resp.json()
    assert body["xp"] == 15
    assert body["new_words"] == 12
    assert body["stats"]["xp_today"] == 15
    assert body["stats"]["streak"] == 1
    assert body["stats"]["words"] == 12

    again = admin_client.post(f"{BASE}/lessons/salutations/complete", json={"mistakes": 2}).json()
    assert again["xp"] == 10
    assert again["new_words"] == 0
    overview = admin_client.get(f"{BASE}/course").json()
    first = overview["units"][0]["lessons"][0]
    assert first["completed"] is True
    assert first["best_mistakes"] == 0
    assert overview["next_lesson"] == "au-cafe"


def _make_all_due():
    with Session(db_module.get_engine()) as s:
        for card in s.exec(select(SrsCard)):
            card.due = datetime.now(UTC) - timedelta(minutes=1)
            s.add(card)
        s.commit()


def test_review_flow(admin_client):
    admin_client.post(f"{BASE}/lessons/salutations/complete", json={"mistakes": 0})
    assert admin_client.get(f"{BASE}/review").json() == []

    _make_all_due()
    queue = admin_client.get(f"{BASE}/review?limit=50").json()
    assert len(queue) == 12
    merci = next(i for i in queue if i["prompt"] == "merci")
    assert merci["mode"] == "fr_en"

    ok = admin_client.post(
        f"{BASE}/review/{merci['id']}", json={"mode": "fr_en", "answer": "thanks"}
    )
    assert ok.json()["correct"] is True
    assert datetime.fromisoformat(ok.json()["next_due"]) > datetime.now(UTC) + timedelta(hours=12)

    oui = next(i for i in queue if i["prompt"] == "oui")
    bad = admin_client.post(f"{BASE}/review/{oui['id']}", json={"mode": "fr_en", "answer": "no"})
    assert bad.json()["correct"] is False
    assert bad.json()["expected"] == "yes"
    # Forgotten cards come back within the same session.
    assert datetime.fromisoformat(bad.json()["next_due"]) < datetime.now(UTC) + timedelta(hours=1)

    stats = admin_client.get(f"{BASE}/stats").json()
    assert stats["due"] == 10
    assert stats["xp_today"] == 16


def test_cannot_review_someone_elses_card(admin_client):
    admin_client.post(f"{BASE}/lessons/salutations/complete", json={"mistakes": 0})
    with Session(db_module.get_engine()) as s:
        card_id = s.exec(select(SrsCard.id)).first()
    guest = {"username": "sam", "display_name": "Sam", "password": "guest password 1"}
    admin_client.post("/api/users", json=guest)
    admin_client.post("/api/auth/logout")
    admin_client.post("/api/auth/login", json={"username": "sam", "password": guest["password"]})
    resp = admin_client.post(f"{BASE}/review/{card_id}", json={"mode": "fr_en", "answer": "x"})
    assert resp.status_code == 404
