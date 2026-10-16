import pytest

from app.modules.poker import engine

BASE = "/api/poker"


def test_preflop_table(admin_client):
    body = admin_client.get(f"{BASE}/preflop").json()
    hands = {h["hand"]: h["equity"] for h in body["hands"]}
    assert len(hands) == 169
    assert abs(hands["AA"][0] - 0.852) < 0.005
    assert hands["AA"][0] > hands["KK"][0] > hands["AKs"][0] > hands["AKo"][0]
    assert all(len(e) == 9 for e in hands.values())


@pytest.fixture
def needs_engine():
    try:
        engine.engine_path()
    except engine.EngineMissing:
        pytest.skip("poker engine not built")


def test_equity_exact(admin_client, needs_engine):
    resp = admin_client.post(f"{BASE}/equity", json={"hands": ["AsAh", "kskh"], "board": ""})
    body = resp.json()
    assert resp.status_code == 200, body
    assert body["exact"] is True
    assert body["players"][0]["equity"] > 0.8


def test_equity_with_random_and_board(admin_client, needs_engine):
    resp = admin_client.post(
        f"{BASE}/equity", json={"hands": ["AhKh", ""], "board": "Qh Jh 2c", "trials": 20000}
    )
    body = resp.json()
    assert body["exact"] is False
    assert body["players"][0]["equity"] > 0.6


def test_equity_rejects_duplicates(admin_client, needs_engine):
    resp = admin_client.post(f"{BASE}/equity", json={"hands": ["AsAh", "AsKd"]})
    assert resp.status_code == 400
    assert "twice" in resp.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [{"hands": ["AsAh"]}, {"hands": ["AsA", "KdKc"]}, {"hands": ["AsAh", ""], "board": "2c3d"}],
)
def test_equity_validation(admin_client, body):
    assert admin_client.post(f"{BASE}/equity", json=body).status_code == 422


def _game(client, **kw):
    return client.post(f"{BASE}/games", json={"name": "Friday", **kw}).json()


def test_home_game_flow(admin_client):
    game = _game(admin_client, default_buy_in=20000)
    gid = game["id"]
    for name in ["Nils", "Sam", "Alex"]:
        game = admin_client.post(
            f"{BASE}/games/{gid}/players", json={"player": name, "buy_in": 20000}
        ).json()
    dup = admin_client.post(f"{BASE}/games/{gid}/players", json={"player": "sam", "buy_in": 1})
    assert dup.status_code == 409

    ids = {e["player"]: e["id"] for e in game["entries"]}
    game = admin_client.post(
        f"{BASE}/games/{gid}/players/{ids['Sam']}/buy-in", json={"amount": 20000}
    ).json()
    assert game["total_in"] == 80000
    assert next(e for e in game["entries"] if e["player"] == "Sam")["buy_ins"] == 2

    early = admin_client.post(f"{BASE}/games/{gid}/settle")
    assert early.status_code == 400

    for name, stack in [("Nils", 50000), ("Sam", 10000), ("Alex", 15000)]:
        game = admin_client.put(
            f"{BASE}/games/{gid}/players/{ids[name]}/cash-out", json={"amount": stack}
        ).json()
    assert game["difference"] == -5000
    assert game["transfers"] is None
    off = admin_client.post(f"{BASE}/games/{gid}/settle")
    assert off.status_code == 400
    assert "under" in off.json()["detail"]

    game = admin_client.put(
        f"{BASE}/games/{gid}/players/{ids['Alex']}/cash-out", json={"amount": 20000}
    ).json()
    assert game["difference"] == 0
    assert {(t["payer"], t["payee"], t["amount"]) for t in game["transfers"]} == {
        ("Sam", "Nils", 30000)
    }

    settled = admin_client.post(f"{BASE}/games/{gid}/settle").json()
    assert settled["settled_at"] is not None
    locked = admin_client.post(
        f"{BASE}/games/{gid}/players/{ids['Sam']}/buy-in", json={"amount": 1}
    )
    assert locked.status_code == 409

    ledger = admin_client.get(f"{BASE}/ledger").json()
    assert [(r["player"], r["net"]) for r in ledger] == [
        ("Nils", 30000),
        ("Alex", 0),
        ("Sam", -30000),
    ]


def test_games_list_and_delete(admin_client):
    gid = _game(admin_client)["id"]
    admin_client.post(f"{BASE}/games/{gid}/players", json={"player": "A", "buy_in": 100})
    games = admin_client.get(f"{BASE}/games").json()
    assert games[0]["players"] == 1 and games[0]["pot"] == 100
    assert admin_client.delete(f"{BASE}/games/{gid}").status_code == 204
    assert admin_client.get(f"{BASE}/games/{gid}").status_code == 404


def test_poker_requires_login(client):
    assert client.get(f"{BASE}/preflop").status_code == 401
