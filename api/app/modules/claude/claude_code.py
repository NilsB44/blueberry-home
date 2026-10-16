"""Reads Claude Code's own session logs (~/.claude/projects/**/*.jsonl on the machine where it
runs) and adds up the tokens each reply used. Mounted read-only into the API container: see
HUB_CLAUDE_LOGS in .env.example.

Each assistant reply is one JSON line with message.usage, message.model and a timestamp. The
same reply can appear more than once (resumed sessions copy history), so replies are counted
once by message id and request id."""

import json
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MAX_FILES = 5000


@dataclass
class Reply:
    day: date
    model: str
    project: str
    session: str
    input: int
    output: int
    cache_read: int
    cache_write_5m: int
    cache_write_1h: int


@dataclass
class _Cached:
    stamp: tuple[float, int]
    replies: dict[str, Reply] = field(default_factory=dict)


_lock = threading.Lock()
_cache: dict[Path, _Cached] = {}


def _int(v) -> int:
    return v if isinstance(v, int) and v > 0 else 0


def parse_line(line: str, tz: ZoneInfo, project: str) -> tuple[str, Reply] | None:
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(entry, dict) or entry.get("type") != "assistant":
        return None
    message = entry.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
        return None
    model = message.get("model")
    if not isinstance(model, str) or model.startswith("<"):  # "<synthetic>" error replies
        return None
    try:
        when = datetime.fromisoformat(str(entry.get("timestamp")).replace("Z", "+00:00"))
    except ValueError:
        return None
    usage = message["usage"]
    creation = usage.get("cache_creation") if isinstance(usage.get("cache_creation"), dict) else {}
    write_1h = _int(creation.get("ephemeral_1h_input_tokens"))
    write_total = _int(usage.get("cache_creation_input_tokens"))
    key = f"{message.get('id')}:{entry.get('requestId')}"
    cwd = entry.get("cwd")
    if isinstance(cwd, str) and cwd.strip("/"):
        project = Path(cwd).name
    return key, Reply(
        day=when.astimezone(tz).date(),
        model=model,
        project=project,
        session=str(entry.get("sessionId", "")),
        input=_int(usage.get("input_tokens")),
        output=_int(usage.get("output_tokens")),
        cache_read=_int(usage.get("cache_read_input_tokens")),
        cache_write_5m=max(write_total - write_1h, 0),
        cache_write_1h=write_1h,
    )


def _project_name(folder: str) -> str:
    # Claude Code names project folders after the path, with "/" turned into "-".
    return folder.rstrip("-").rsplit("-", 1)[-1] or folder


def read_replies(root: Path, tz: ZoneInfo) -> list[Reply]:
    """Every reply in the logs, re-reading only files that changed since last time."""
    if not root.is_dir():
        return []
    files = sorted(root.rglob("*.jsonl"))[:MAX_FILES]
    with _lock:
        seen: dict[str, Reply] = {}
        for path in files:
            try:
                st = path.stat()
            except OSError:
                continue
            stamp = (st.st_mtime, st.st_size)
            cached = _cache.get(path)
            if cached is None or cached.stamp != stamp:
                cached = _Cached(stamp)
                rel = path.relative_to(root).parts
                project = _project_name(rel[0]) if len(rel) > 1 else "other"
                try:
                    with path.open(encoding="utf-8", errors="replace") as f:
                        for line in f:
                            if parsed := parse_line(line, tz, project):
                                cached.replies[parsed[0]] = parsed[1]
                except OSError:
                    continue
                _cache[path] = cached
            seen.update(cached.replies)
        for gone in set(_cache) - set(files):
            del _cache[gone]
    return list(seen.values())
