import json
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlmodel import col, func, select

from app.auth.deps import COOKIE_NAME, CurrentUser, DbSession, user_for_token
from app.auth.models import User
from app.auth.network import is_trusted
from app.modules.security import tracker
from app.modules.tetris.models import TetrisScore
from app.modules.tetris.rooms import MAX_PLAYERS, Player, rooms

router = APIRouter(prefix="/api/tetris", tags=["tetris"])


class RoomSummary(BaseModel):
    code: str
    host: str | None
    players: list[str]
    started: bool
    full: bool


class NewScore(BaseModel):
    score: int = Field(ge=0, le=10_000_000)
    lines: int = Field(ge=0, le=100_000)
    level: int = Field(ge=1, le=100)


class ScoreOut(BaseModel):
    name: str
    score: int
    lines: int
    level: int
    mine: bool


class Scores(BaseModel):
    top: list[ScoreOut]
    best: int | None


@router.get("/rooms")
def list_rooms(_: CurrentUser) -> list[RoomSummary]:
    rooms.prune()
    return [RoomSummary(**r.summary()) for r in rooms.rooms.values()]


@router.post("/rooms", status_code=status.HTTP_201_CREATED)
def create_room(_: CurrentUser) -> RoomSummary:
    room = rooms.create()
    if room is None:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many rooms open right now")
    return RoomSummary(**room.summary())


@router.get("/scores")
def scores(user: CurrentUser, db: DbSession) -> Scores:
    rows = db.exec(
        select(TetrisScore, User)
        .join(User, col(User.id) == TetrisScore.user_id)
        .order_by(col(TetrisScore.score).desc(), col(TetrisScore.id))
        .limit(10)
    ).all()
    best = db.exec(select(func.max(TetrisScore.score)).where(TetrisScore.user_id == user.id)).one()
    return Scores(
        top=[
            ScoreOut(
                name=u.display_name,
                score=s.score,
                lines=s.lines,
                level=s.level,
                mine=u.id == user.id,
            )
            for s, u in rows
        ],
        best=best,
    )


@router.post("/scores", status_code=status.HTTP_201_CREATED)
def add_score(body: NewScore, user: CurrentUser, db: DbSession) -> Scores:
    if body.score > 0:
        db.add(TetrisScore(user_id=user.id, **body.model_dump()))
        db.commit()
    return scores(user, db)


def _same_origin(ws: WebSocket) -> bool:
    # Browsers send cookies with cross-site WebSocket handshakes in some cases, so only let in
    # pages served by the hub itself.
    origin = ws.headers.get("origin")
    if origin is None:
        return True  # not a browser
    return urlsplit(origin).netloc == ws.headers.get("host")


@router.websocket("/rooms/{code}/ws")
async def play(ws: WebSocket, code: str, db: DbSession) -> None:
    # The LocalNetworkOnly middleware only sees HTTP requests, so check here too. Games are
    # for the home Wi-Fi only, so away access doesn't reach them.
    host = ws.client.host if ws.client else None
    if not is_trusted(host) or not _same_origin(ws):
        tracker.record("blocked", host, ws.url.path)
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user = user_for_token(db, ws.cookies.get(COOKIE_NAME))
    if user is None or user.id is None:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id, name = user.id, user.display_name
    db.close()  # don't hold a database transaction open for the whole game

    room = rooms.get(code)
    await ws.accept()
    if room is None:
        await ws.send_text(json.dumps({"t": "error", "message": "That room has closed"}))
        await ws.close()
        return
    if len(room.players) >= MAX_PLAYERS and user_id not in room.players:
        await ws.send_text(json.dumps({"t": "error", "message": "That room is full"}))
        await ws.close()
        return

    player = Player(user_id=user_id, name=name, ws=ws)
    await room.join(player)
    try:
        while True:
            text = await ws.receive_text()
            if len(text) > 4096:
                continue
            try:
                msg = json.loads(text)
            except ValueError:
                continue
            if isinstance(msg, dict):
                await room.handle(player, msg)
    except WebSocketDisconnect:
        pass
    finally:
        await room.leave(player)
        rooms.drop_if_empty(room)
