"""Slows down password guessing: after too many wrong passwords from one address, or for one
username, logins are refused for a while. Kept in memory: a restart clears it, which is fine
for a hub only the home network can reach."""

import threading
import time

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
MAX_KEYS = 5000

_lock = threading.Lock()
# key -> timestamps of recent failures
_failures: dict[str, list[float]] = {}


def _recent(key: str, now: float) -> list[float]:
    times = [t for t in _failures.get(key, []) if now - t < WINDOW_SECONDS]
    if times:
        _failures[key] = times
    else:
        _failures.pop(key, None)
    return times


def locked_for(ip: str | None, username: str) -> int:
    """Seconds until a login may be tried again, or 0."""
    now = time.monotonic()
    with _lock:
        waits = [
            int(WINDOW_SECONDS - (now - times[0])) + 1
            for key in (f"ip:{ip}", f"user:{username.lower()}")
            if len(times := _recent(key, now)) >= MAX_FAILURES
        ]
    return max(waits, default=0)


def record_failure(ip: str | None, username: str) -> bool:
    """Count a wrong password. True if this one just triggered a lockout."""
    now = time.monotonic()
    triggered = False
    with _lock:
        for key in (f"ip:{ip}", f"user:{username.lower()}"):
            times = _recent(key, now)
            # A flood of made-up usernames can't grow this without bound; the per-address
            # count still catches it.
            if not times and len(_failures) >= MAX_KEYS and key.startswith("user:"):
                continue
            times.append(now)
            _failures[key] = times[-MAX_FAILURES * 4 :]
            triggered = triggered or len(times) == MAX_FAILURES
    return triggered


def clear() -> None:
    with _lock:
        _failures.clear()
