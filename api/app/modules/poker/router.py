"""Poker toolkit: pre-flop equity chart, equity calculator, and home-game bookkeeping."""

import json
import re
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlmodel import select

from app.auth.deps import CurrentUser, DbSession
from app.config import get_settings
from app.modules.poker import engine
from app.modules.poker.models import PokerEntry, PokerGame
from app.modules.poker.settle import settle

router = APIRouter(prefix="/api/poker", tags=["poker"])

CARDS = re.compile(r"^([2-9TJQKA][cdhs])*$")


# ---------- pre-flop chart and calculator ----------


@lru_cache
def _preflop() -> dict:
    return json.loads((get_settings().content_dir / "poker/preflop.json").read_text())


@router.get("/preflop")
def preflop(_: CurrentUser) -> dict:
    """Equity of each of the 169 starting hands against 1–9 random opponents."""
    return _preflop()


def _clean_cards(text: str) -> str:
    s = re.sub(r"\s+", "", text).replace("10", "T")
    s = "".join(ch.upper() if i % 2 == 0 else ch.lower() for i, ch in enumerate(s))
    if not CARDS.match(s):
        raise ValueError(f"can't read cards {text!r}; use e.g. AhKd")
    return s


class EquityIn(BaseModel):
    hands: list[str] = Field(min_length=2, max_length=10)  # "" for a random hand
    board: str = ""
    trials: int = Field(default=200_000, ge=1_000, le=2_000_000)

    @field_validator("hands")
    @classmethod
    def _hands(cls, v: list[str]) -> list[str]:
        out = [_clean_cards(h) for h in v]
        if any(h and len(h) != 4 for h in out):
            raise ValueError("each hand is two cards, or empty for random")
        return out

    @field_validator("board")
    @classmethod
    def _board(cls, v: str) -> str:
        out = _clean_cards(v)
        if len(out) // 2 not in (0, 3, 4, 5):
            raise ValueError("the board has 0, 3, 4 or 5 cards")
        return out


@router.post("/equity")
async def equity(body: EquityIn, _: CurrentUser) -> dict:
    try:
        return await engine.equity(body.hands, body.board, body.trials)
    except engine.EngineMissing as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except engine.EngineError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ---------- home games ----------


class GameIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    currency: str = Field(default="SEK", pattern=r"^[A-Z]{3}$")
    default_buy_in: int = Field(default=0, ge=0, le=100_000_000)


class PlayerIn(BaseModel):
    player: str = Field(min_length=1, max_length=40)
    buy_in: int = Field(ge=0, le=100_000_000)


class AmountIn(BaseModel):
    amount: int = Field(ge=0, le=100_000_000)


class EntryOut(BaseModel):
    id: int
    player: str
    buy_in: int
    buy_ins: int
    cash_out: int | None
    net: int | None


class TransferOut(BaseModel):
    payer: str
    payee: str
    amount: int


class GameOut(BaseModel):
    id: int
    name: str
    currency: str
    default_buy_in: int
    created_at: datetime
    settled_at: datetime | None
    entries: list[EntryOut]
    total_in: int
    total_out: int
    # Positive: chips on the table don't add up to money in (someone miscounted).
    difference: int | None
    transfers: list[TransferOut] | None


class GameSummary(BaseModel):
    id: int
    name: str
    currency: str
    created_at: datetime
    settled_at: datetime | None
    players: int
    pot: int


def _game(db: DbSession, game_id: int, *, open_only: bool = False) -> PokerGame:
    game = db.get(PokerGame, game_id)
    if game is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such game")
    if open_only and game.settled_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This game is already settled")
    return game


def _entries(db: DbSession, game_id: int) -> list[PokerEntry]:
    return list(
        db.exec(select(PokerEntry).where(PokerEntry.game_id == game_id).order_by(PokerEntry.id))
    )


def _entry(db: DbSession, game_id: int, entry_id: int) -> PokerEntry:
    entry = db.get(PokerEntry, entry_id)
    if entry is None or entry.game_id != game_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such player in this game")
    return entry


def _out(db: DbSession, game: PokerGame) -> GameOut:
    entries = _entries(db, game.id)
    total_in = sum(e.buy_in for e in entries)
    total_out = sum(e.cash_out or 0 for e in entries)
    all_out = bool(entries) and all(e.cash_out is not None for e in entries)
    difference = total_out - total_in if all_out else None
    transfers = None
    if all_out and difference == 0:
        transfers = [
            TransferOut(payer=t.payer, payee=t.payee, amount=t.amount)
            for t in settle({e.player: e.cash_out - e.buy_in for e in entries})
        ]
    return GameOut(
        id=game.id,
        name=game.name,
        currency=game.currency,
        default_buy_in=game.default_buy_in,
        created_at=game.created_at,
        settled_at=game.settled_at,
        entries=[
            EntryOut(
                id=e.id,
                player=e.player,
                buy_in=e.buy_in,
                buy_ins=e.buy_ins,
                cash_out=e.cash_out,
                net=None if e.cash_out is None else e.cash_out - e.buy_in,
            )
            for e in entries
        ],
        total_in=total_in,
        total_out=total_out,
        difference=difference,
        transfers=transfers,
    )


@router.get("/games")
def list_games(_: CurrentUser, db: DbSession) -> list[GameSummary]:
    games = db.exec(select(PokerGame).order_by(PokerGame.created_at.desc())).all()
    out = []
    for g in games:
        entries = _entries(db, g.id)
        out.append(
            GameSummary(
                id=g.id,
                name=g.name,
                currency=g.currency,
                created_at=g.created_at,
                settled_at=g.settled_at,
                players=len(entries),
                pot=sum(e.buy_in for e in entries),
            )
        )
    return out


@router.post("/games", status_code=status.HTTP_201_CREATED)
def create_game(body: GameIn, user: CurrentUser, db: DbSession) -> GameOut:
    game = PokerGame(**body.model_dump(), created_by=user.id)
    db.add(game)
    db.commit()
    db.refresh(game)
    return _out(db, game)


@router.get("/games/{game_id}")
def get_game(game_id: int, _: CurrentUser, db: DbSession) -> GameOut:
    return _out(db, _game(db, game_id))


@router.delete("/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(game_id: int, user: CurrentUser, db: DbSession) -> None:
    game = _game(db, game_id)
    if game.created_by != user.id and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the host or an admin can delete it")
    for e in _entries(db, game.id):
        db.delete(e)
    db.delete(game)
    db.commit()


@router.post("/games/{game_id}/players", status_code=status.HTTP_201_CREATED)
def add_player(game_id: int, body: PlayerIn, _: CurrentUser, db: DbSession) -> GameOut:
    game = _game(db, game_id, open_only=True)
    name = body.player.strip()
    if any(e.player.lower() == name.lower() for e in _entries(db, game.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{name} is already in this game")
    db.add(
        PokerEntry(
            game_id=game.id, player=name, buy_in=body.buy_in, buy_ins=1 if body.buy_in else 0
        )
    )
    db.commit()
    return _out(db, game)


@router.post("/games/{game_id}/players/{entry_id}/buy-in")
def add_buy_in(
    game_id: int, entry_id: int, body: AmountIn, _: CurrentUser, db: DbSession
) -> GameOut:
    game = _game(db, game_id, open_only=True)
    entry = _entry(db, game.id, entry_id)
    if body.amount == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A buy-in must be more than zero")
    entry.buy_in += body.amount
    entry.buy_ins += 1
    db.add(entry)
    db.commit()
    return _out(db, game)


@router.put("/games/{game_id}/players/{entry_id}/cash-out")
def cash_out(game_id: int, entry_id: int, body: AmountIn, _: CurrentUser, db: DbSession) -> GameOut:
    game = _game(db, game_id, open_only=True)
    entry = _entry(db, game.id, entry_id)
    entry.cash_out = body.amount
    db.add(entry)
    db.commit()
    return _out(db, game)


@router.delete("/games/{game_id}/players/{entry_id}")
def remove_player(game_id: int, entry_id: int, _: CurrentUser, db: DbSession) -> GameOut:
    game = _game(db, game_id, open_only=True)
    db.delete(_entry(db, game.id, entry_id))
    db.commit()
    return _out(db, game)


@router.post("/games/{game_id}/settle")
def settle_game(game_id: int, _: CurrentUser, db: DbSession) -> GameOut:
    game = _game(db, game_id, open_only=True)
    out = _out(db, game)
    if out.difference is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter every player's final stack first")
    if out.difference != 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Final stacks are {abs(out.difference) / 100:.2f} {game.currency} "
            f"{'over' if out.difference > 0 else 'under'} the money paid in. Recount the chips.",
        )
    game.settled_at = datetime.now(UTC)
    db.add(game)
    db.commit()
    return _out(db, game)


class LedgerRow(BaseModel):
    player: str
    currency: str
    games: int
    buy_in: int
    net: int
    best: int
    worst: int


@router.get("/ledger")
def ledger(_: CurrentUser, db: DbSession) -> list[LedgerRow]:
    """Lifetime results per player across settled games, per currency."""
    rows = db.exec(
        select(PokerEntry, PokerGame)
        .join(PokerGame, PokerEntry.game_id == PokerGame.id)
        .where(PokerGame.settled_at.is_not(None))
    ).all()
    agg: dict[tuple[str, str], LedgerRow] = {}
    for e, g in rows:
        net = e.cash_out - e.buy_in
        key = (e.player.lower(), g.currency)
        row = agg.get(key) or LedgerRow(
            player=e.player, currency=g.currency, games=0, buy_in=0, net=0, best=net, worst=net
        )
        row.games += 1
        row.buy_in += e.buy_in
        row.net += net
        row.best = max(row.best, net)
        row.worst = min(row.worst, net)
        agg[key] = row
    return sorted(agg.values(), key=lambda r: r.net, reverse=True)
