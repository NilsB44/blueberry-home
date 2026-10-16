"""Counts refused requests and failed logins in memory, written to the database once a minute.

Writing a row per refused request would let anyone who can reach the Pi wear out its storage, so
attempts are added up per address per day, and the number of distinct addresses held between
writes is capped."""

import threading
from datetime import UTC, date, datetime

from sqlmodel import Session, select

from app.modules.security.models import AccessAttempt

MAX_KEYS = 2000
OVERFLOW_IP = "(many others)"

_lock = threading.Lock()
# Flushes come from the scheduler and from requests; one at a time so rows aren't inserted twice.
_flush_lock = threading.Lock()
# (kind, ip, day) -> [count, detail, last_seen]
_pending: dict[tuple[str, str, date], list] = {}


def record(kind: str, ip: str | None, detail: str = "") -> None:
    now = datetime.now(UTC)
    ip = (ip or "unknown")[:64]
    with _lock:
        key = (kind, ip, now.date())
        if key not in _pending and len(_pending) >= MAX_KEYS:
            key = (kind, OVERFLOW_IP, now.date())
        entry = _pending.setdefault(key, [0, "", now])
        entry[0] += 1
        entry[1] = detail[:200]
        entry[2] = now


def flush(session: Session) -> None:
    with _flush_lock:
        _flush(session)


def _flush(session: Session) -> None:
    with _lock:
        pending = dict(_pending)
        _pending.clear()
    for (kind, ip, day), (count, detail, last_seen) in pending.items():
        row = session.exec(
            select(AccessAttempt).where(
                AccessAttempt.kind == kind, AccessAttempt.ip == ip, AccessAttempt.day == day
            )
        ).first()
        if row is None:
            row = AccessAttempt(kind=kind, ip=ip, day=day)
        row.count += count
        row.detail = detail
        row.last_seen = last_seen
        session.add(row)
    session.commit()


def clear() -> None:
    with _lock:
        _pending.clear()
