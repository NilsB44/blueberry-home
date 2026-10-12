"""Runs the Rust equity engine (engines/poker) as a subprocess and parses its JSON."""

import asyncio
import json
import shutil
from pathlib import Path

from app.config import get_settings

_DEV_BUILD = Path(__file__).resolve().parents[4] / "engines/poker/target/release/poker-engine"


class EngineError(Exception):
    pass


class EngineMissing(EngineError):
    pass


def engine_path() -> str:
    configured = get_settings().poker_engine
    if found := shutil.which(configured):
        return found
    if _DEV_BUILD.exists():
        return str(_DEV_BUILD)
    raise EngineMissing(
        "Poker engine not found. Build it with `cargo build --release` in engines/poker."
    )


async def equity(hands: list[str], board: str, trials: int) -> dict:
    args = ["equity", "--hands", ",".join(h or "random" for h in hands), "--trials", str(trials)]
    if board:
        args += ["--board", board]
    proc = await asyncio.create_subprocess_exec(
        engine_path(), *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=20)
    except TimeoutError as exc:
        proc.kill()
        raise EngineError("The calculation took too long") from exc
    if proc.returncode != 0:
        raise EngineError(err.decode().strip() or "engine failed")
    return json.loads(out)
