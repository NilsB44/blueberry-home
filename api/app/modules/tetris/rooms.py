"""Multiplayer rooms, kept in memory: a game night doesn't need to survive a restart.

Every player runs the game on their own device from the same seed, so everyone gets the same
pieces. The server owns the room: who's in, who's still alive, who won, and where garbage and
power-ups go. Players only ever talk to the server, never to each other.
"""

import asyncio
import json
import random
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

MAX_PLAYERS = 4
MAX_ROOMS = 20
# A room nobody joins disappears after this many seconds.
EMPTY_ROOM_TTL = 120
CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
BOARD = re.compile(r"^[0-8]{200}$")
# Power-ups that hit opponents; the rest only change your own board.
ATTACK_POWERS = {"rush"}


@dataclass
class Player:
    user_id: int
    name: str
    ws: WebSocket
    playing: bool = False
    alive: bool = False
    board: str = ""
    score: int = 0
    lines: int = 0
    place: int | None = None
    wins: int = 0

    def public(self) -> dict[str, Any]:
        return {
            "id": self.user_id,
            "name": self.name,
            "playing": self.playing,
            "alive": self.alive,
            "score": self.score,
            "lines": self.lines,
            "place": self.place,
            "wins": self.wins,
        }


@dataclass
class Room:
    code: str
    created: float = field(default_factory=time.monotonic)
    host: int | None = None
    players: dict[int, Player] = field(default_factory=dict)
    started: bool = False
    seed: int = 0
    round: int = 0
    winner: str | None = None

    def summary(self) -> dict[str, Any]:
        host = self.players.get(self.host) if self.host is not None else None
        return {
            "code": self.code,
            "host": host.name if host else None,
            "players": [p.name for p in self.players.values()],
            "started": self.started,
            "full": len(self.players) >= MAX_PLAYERS,
        }

    def lobby(self) -> dict[str, Any]:
        return {
            "t": "lobby",
            "code": self.code,
            "host": self.host,
            "started": self.started,
            "round": self.round,
            "winner": self.winner,
            "players": [p.public() for p in self.players.values()],
        }

    async def send(self, player: Player, msg: dict[str, Any]) -> None:
        try:
            await player.ws.send_text(json.dumps(msg))
        except Exception:  # noqa: BLE001 - the receive loop notices the drop and cleans up
            pass

    async def broadcast(self, msg: dict[str, Any], skip: int | None = None) -> None:
        await asyncio.gather(
            *(self.send(p, msg) for p in list(self.players.values()) if p.user_id != skip)
        )

    # --- events -----------------------------------------------------------------------------

    async def join(self, player: Player) -> None:
        old = self.players.get(player.user_id)
        if old is not None:
            # Same person in a second tab: the newest connection wins.
            await self.send(old, {"t": "error", "message": "You joined from another tab"})
            try:
                await old.ws.close()
            except Exception:  # noqa: BLE001
                pass
            player.wins = old.wins
        self.players[player.user_id] = player
        if self.host is None or self.host not in self.players:
            self.host = player.user_id
        await self.send(player, {"t": "hello", "you": player.user_id})
        if self.started:
            await self.send(player, {"t": "watch", "seed": self.seed, "round": self.round})
        await self.broadcast(self.lobby())

    async def leave(self, player: Player) -> None:
        if self.players.get(player.user_id) is not player:
            return  # replaced by a newer connection
        del self.players[player.user_id]
        if self.host == player.user_id:
            self.host = next(iter(self.players), None)
        if self.started and player.playing and player.alive:
            player.alive = False
            await self._check_end()
        await self.broadcast(self.lobby())

    async def handle(self, player: Player, msg: dict[str, Any]) -> None:
        kind = msg.get("t")
        if kind == "start":
            await self._start(player)
        elif kind == "state" and self.started and player.alive:
            board = msg.get("board")
            if isinstance(board, str) and BOARD.match(board):
                player.board = board
            player.score = _int(msg.get("score"), 0, 10_000_000)
            player.lines = _int(msg.get("lines"), 0, 100_000)
            await self.broadcast(
                {
                    "t": "state",
                    "id": player.user_id,
                    "board": player.board,
                    "score": player.score,
                    "lines": player.lines,
                },
                skip=player.user_id,
            )
        elif kind == "attack" and self.started and player.alive:
            lines = _int(msg.get("lines"), 0, 4)
            targets = [p for p in self._alive() if p.user_id != player.user_id]
            if lines and targets:
                target = random.choice(targets)
                await self.send(target, {"t": "garbage", "lines": lines, "from": player.name})
                await self.broadcast(
                    {"t": "attacked", "from": player.user_id, "to": target.user_id, "lines": lines}
                )
        elif kind == "power" and self.started and player.alive:
            power = msg.get("kind")
            if power in ATTACK_POWERS:
                for target in self._alive():
                    if target.user_id != player.user_id:
                        await self.send(target, {"t": "power", "kind": power, "from": player.name})
        elif kind == "over" and self.started and player.alive:
            player.alive = False
            player.place = len(self._alive()) + 1
            await self._check_end()
            await self.broadcast(self.lobby())

    async def _start(self, player: Player) -> None:
        if player.user_id != self.host or self.started:
            return
        if len(self.players) < 2:
            await self.send(player, {"t": "error", "message": "Wait for someone to join first"})
            return
        self.started = True
        self.round += 1
        self.seed = secrets.randbelow(2**31)
        self.winner = None
        for p in self.players.values():
            p.playing = p.alive = True
            p.board, p.score, p.lines, p.place = "", 0, 0, None
        await self.broadcast(self.lobby())
        await self.broadcast({"t": "start", "seed": self.seed, "round": self.round})

    def _alive(self) -> list[Player]:
        return [p for p in self.players.values() if p.playing and p.alive]

    async def _check_end(self) -> None:
        alive = self._alive()
        if len(alive) > 1:
            return
        self.started = False
        winner_id = alive[0].user_id if alive else None
        if alive:
            alive[0].place = 1
            alive[0].wins += 1
            alive[0].alive = False
            self.winner = alive[0].name
        else:
            self.winner = None
        await self.broadcast({"t": "end", "winner": self.winner, "id": winner_id})


def _int(value: Any, lo: int, hi: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        return lo
    return max(lo, min(hi, value))


class Rooms:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}

    def prune(self) -> None:
        now = time.monotonic()
        for code, room in list(self.rooms.items()):
            if not room.players and now - room.created > EMPTY_ROOM_TTL:
                del self.rooms[code]

    def create(self) -> Room | None:
        self.prune()
        if len(self.rooms) >= MAX_ROOMS:
            return None
        while True:
            code = "".join(secrets.choice(CODE_LETTERS) for _ in range(4))
            if code not in self.rooms:
                break
        room = Room(code)
        self.rooms[code] = room
        return room

    def get(self, code: str) -> Room | None:
        return self.rooms.get(code.upper())

    def drop_if_empty(self, room: Room) -> None:
        if not room.players and self.rooms.get(room.code) is room:
            del self.rooms[room.code]


rooms = Rooms()
