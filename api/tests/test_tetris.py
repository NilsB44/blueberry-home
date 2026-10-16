from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.modules.tetris.rooms import rooms

BASE = "/api/tetris"
COOKIE = "hub_session"


@pytest.fixture(autouse=True)
def no_rooms():
    rooms.rooms.clear()
    yield
    rooms.rooms.clear()


@contextmanager
def _as(client, token):
    """Act as another device on the same client, so every socket shares one event loop."""
    mine = client.cookies.get(COOKIE)
    _use(client, token)
    try:
        yield client
    finally:
        _use(client, mine)


def _use(client, token):
    client.cookies.clear()
    client.cookies.set(COOKIE, token)


def _second_device(client):
    """A second phone: returns its cookie and who it is."""
    mine = client.cookies.get(COOKIE)
    client.cookies.clear()
    them = client.post("/api/auth/device").json()
    token = client.cookies.get(COOKIE)
    _use(client, mine)
    return token, them


def _recv_until(ws, kind):
    while True:
        msg = ws.receive_json()
        if msg["t"] == kind:
            return msg


def test_scores(client):
    client.post("/api/auth/device")
    assert client.get(f"{BASE}/scores").json() == {"top": [], "best": None}
    client.post(f"{BASE}/scores", json={"score": 1200, "lines": 10, "level": 2})
    body = client.post(f"{BASE}/scores", json={"score": 800, "lines": 6, "level": 1}).json()
    assert [s["score"] for s in body["top"]] == [1200, 800]
    assert body["best"] == 1200
    assert body["top"][0]["mine"] is True
    assert (
        client.post(f"{BASE}/scores", json={"score": -1, "lines": 0, "level": 1}).status_code == 422
    )


def test_rooms_need_a_person(client):
    assert client.get(f"{BASE}/rooms").status_code == 401
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"{BASE}/rooms/ABCD/ws") as ws:
            ws.receive_json()


def test_websocket_refuses_other_sites(client):
    client.post("/api/auth/device")
    code = client.post(f"{BASE}/rooms").json()["code"]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"{BASE}/rooms/{code}/ws", headers={"origin": "https://evil.example"}
        ) as ws:
            ws.receive_json()


def test_websocket_refuses_outside_addresses(client):
    client.post("/api/auth/device")
    code = client.post(f"{BASE}/rooms").json()["code"]
    cookie = client.cookies.get("hub_session")
    with TestClient(app, client=("8.8.8.8", 50000)) as outsider:
        outsider.cookies.set("hub_session", cookie)
        with pytest.raises(WebSocketDisconnect):
            with outsider.websocket_connect(f"{BASE}/rooms/{code}/ws") as ws:
                ws.receive_json()


def test_two_player_round(client):
    me = client.post("/api/auth/device").json()
    code = client.post(f"{BASE}/rooms").json()["code"]
    other, them = _second_device(client)

    with client.websocket_connect(f"{BASE}/rooms/{code}/ws") as a:
        assert a.receive_json() == {"t": "hello", "you": me["id"]}
        lobby = _recv_until(a, "lobby")
        assert lobby["host"] == me["id"]

        # Alone: can't start yet.
        a.send_json({"t": "start"})
        assert _recv_until(a, "error")["message"].startswith("Wait")

        with _as(client, other):
            b = client.websocket_connect(f"{BASE}/rooms/{code}/ws")
        with b:
            _recv_until(b, "lobby")
            assert len(_recv_until(a, "lobby")["players"]) == 2
            assert client.get(f"{BASE}/rooms").json()[0]["players"] == [
                me["display_name"],
                them["display_name"],
            ]

            # Only the host starts, and both get the same seed.
            b.send_json({"t": "start"})
            a.send_json({"t": "start"})
            seed = _recv_until(a, "start")["seed"]
            assert _recv_until(b, "start")["seed"] == seed

            # Boards are relayed to the others.
            a.send_json({"t": "state", "board": "0" * 190 + "1" * 10, "score": 40, "lines": 1})
            state = _recv_until(b, "state")
            assert state["id"] == me["id"] and state["score"] == 40

            # A bad board is dropped, numbers clamped.
            a.send_json({"t": "state", "board": "<script>", "score": 10**12, "lines": "x"})
            state = _recv_until(b, "state")
            assert state["board"] == "0" * 190 + "1" * 10 and state["score"] == 10_000_000

            # Garbage goes to the opponent, capped at 4 lines.
            a.send_json({"t": "attack", "lines": 9})
            assert _recv_until(b, "garbage") == {
                "t": "garbage",
                "lines": 4,
                "from": me["display_name"],
            }
            a.send_json({"t": "power", "kind": "rush"})
            assert _recv_until(b, "power")["kind"] == "rush"

            # B tops out: A wins.
            b.send_json({"t": "over"})
            assert _recv_until(a, "end")["winner"] == me["display_name"]
            lobby = _recv_until(a, "lobby")
            assert not lobby["started"]
            assert {p["id"]: p["wins"] for p in lobby["players"]} == {me["id"]: 1, them["id"]: 0}

        # B left: A is alone again.
        assert len(_recv_until(a, "lobby")["players"]) == 1
    assert client.get(f"{BASE}/rooms").json() == []


def test_leaving_mid_game_hands_the_win_over(client):
    me = client.post("/api/auth/device").json()
    code = client.post(f"{BASE}/rooms").json()["code"]
    other, _ = _second_device(client)
    with client.websocket_connect(f"{BASE}/rooms/{code}/ws") as a:
        with _as(client, other):
            b = client.websocket_connect(f"{BASE}/rooms/{code}/ws")
        with b:
            _recv_until(b, "lobby")
            a.send_json({"t": "start"})
            _recv_until(b, "start")
        assert _recv_until(a, "end")["winner"] == me["display_name"]


def test_unknown_room(client):
    client.post("/api/auth/device")
    with client.websocket_connect(f"{BASE}/rooms/ZZZZ/ws") as ws:
        assert ws.receive_json()["message"] == "That room has closed"
