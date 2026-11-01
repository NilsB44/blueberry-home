"""Watches the internet connection, measures its speed now and then, and reads the Pi's scans
of the Wi-Fi (scripts/pi-network-scan.py) into the device list.

Like the security scheduler, a background task in the hub's one process: no cron needed."""

import asyncio
import json
import logging
import socket
import statistics
import threading
import time
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, func, select

from app.config import get_settings
from app.db import get_engine
from app.modules.network.models import InternetHour, NetworkDevice, Outage, SpeedTest

log = logging.getLogger(__name__)

TICK_SECONDS = 60
PROBE_TIMEOUT = 3.0
# One failed minute can be a blip; two in a row is an outage.
FAILURES_FOR_OUTAGE = 2
FLUSH_EVERY = timedelta(minutes=15)
KEEP = timedelta(days=90)
DOWNLOAD_BYTES = 25_000_000
UPLOAD_BYTES = 8_000_000
PING_SAMPLES = 5

# One speed test at a time, whether scheduled or asked for.
speedtest_running = threading.Lock()
_lock = threading.Lock()


class _State:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        # hour -> [checks, failures, latency total, latency max], not yet written.
        self.hours: dict[datetime, list[float]] = {}
        self.flushed_at = datetime.now(UTC)
        self.failures_in_row = 0
        self.first_failure: datetime | None = None
        self.up: bool | None = None
        self.latency_ms: float | None = None
        self.checked_at: datetime | None = None
        self.scan_mtime: float | None = None
        self.scan: Scan | None = None


class ScannedDevice(BaseModel):
    mac: str = Field(pattern=r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
    ip: str = Field(max_length=64)
    hostname: str = Field(default="", max_length=64)
    is_pi: bool = False


class Scan(BaseModel):
    generated_at: datetime
    interface: str = Field(default="", max_length=32)
    network: str = Field(default="", max_length=64)
    gateway: str = Field(default="", max_length=64)
    devices: list[ScannedDevice] = Field(max_length=4096)


state = _State()


def _hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# --- Internet -----------------------------------------------------------------------------


def probe() -> float | None:
    """Milliseconds to open a connection to the first probe host that answers, or None."""
    for host in get_settings().network_probe_hosts:
        start = time.perf_counter()
        try:
            with socket.create_connection((host, 443), timeout=PROBE_TIMEOUT):
                return round((time.perf_counter() - start) * 1000, 1)
        except OSError:
            continue
    return None


def record_probe(session: Session, latency_ms: float | None, now: datetime) -> None:
    with _lock:
        entry = state.hours.setdefault(_hour(now), [0, 0, 0.0, 0.0])
        entry[0] += 1
        state.checked_at = now
        state.latency_ms = latency_ms
        if latency_ms is None:
            entry[1] += 1
            state.failures_in_row += 1
            if state.failures_in_row == 1:
                state.first_failure = now
        else:
            entry[2] += latency_ms
            entry[3] = max(entry[3], latency_ms)
            state.failures_in_row = 0
        was_up = state.up
        state.up = state.failures_in_row < FAILURES_FOR_OUTAGE
        started = state.first_failure

    if was_up is not False and not state.up:
        # A hub restarted mid-outage finds it still open and carries on with it.
        if session.exec(select(Outage).where(Outage.ended_at.is_(None))).first() is None:
            session.add(Outage(started_at=started or now))
            session.commit()
    elif state.up and latency_ms is not None:
        # Close the outage, including one left open when the hub restarted mid-outage.
        open_ = session.exec(select(Outage).where(Outage.ended_at.is_(None))).all()
        for outage in open_:
            outage.ended_at = now
            session.add(outage)
        if open_:
            session.commit()
    if now - state.flushed_at >= FLUSH_EVERY or any(h < _hour(now) for h in state.hours):
        flush(session, now)


def flush(session: Session, now: datetime | None = None) -> None:
    with _lock:
        pending = state.hours
        state.hours = {}
        state.flushed_at = now or datetime.now(UTC)
    for hour, (checks, failures, total, peak) in pending.items():
        row = session.get(InternetHour, hour) or InternetHour(hour=hour)
        row.checks += int(checks)
        row.failures += int(failures)
        row.latency_ms_total += total
        row.latency_ms_max = max(row.latency_ms_max, peak)
        session.add(row)
    session.commit()


def hours_since(session: Session, since: datetime) -> list[InternetHour]:
    """Hourly totals from `since`, including what's still in memory."""
    rows = {
        _aware(r.hour): r
        for r in session.exec(select(InternetHour).where(InternetHour.hour >= _hour(since)))
    }
    with _lock:
        pending = dict(state.hours)
    for hour, (checks, failures, total, peak) in pending.items():
        if hour < _hour(since):
            continue
        row = rows.get(hour)
        if row is None:
            rows[hour] = InternetHour(
                hour=hour,
                checks=int(checks),
                failures=int(failures),
                latency_ms_total=total,
                latency_ms_max=peak,
            )
        else:
            rows[hour] = InternetHour(
                hour=hour,
                checks=row.checks + int(checks),
                failures=row.failures + int(failures),
                latency_ms_total=row.latency_ms_total + total,
                latency_ms_max=max(row.latency_ms_max, peak),
            )
    return [rows[h] for h in sorted(rows)]


def uptime(rows: list[InternetHour]) -> float | None:
    checks = sum(r.checks for r in rows)
    return round((checks - sum(r.failures for r in rows)) / checks, 5) if checks else None


# --- Speed test ---------------------------------------------------------------------------


def measure_speed(client: httpx.Client, base: str) -> tuple[float, float, float]:
    """(ping ms, download Mbit/s, upload Mbit/s) against a Cloudflare-style speed endpoint."""
    pings = []
    for _ in range(PING_SAMPLES):
        start = time.perf_counter()
        client.get(f"{base}/__down", params={"bytes": 0}).raise_for_status()
        pings.append((time.perf_counter() - start) * 1000)

    start = time.perf_counter()
    received = 0
    with client.stream("GET", f"{base}/__down", params={"bytes": DOWNLOAD_BYTES}) as resp:
        resp.raise_for_status()
        for chunk in resp.iter_bytes():
            received += len(chunk)
    down = received * 8 / (time.perf_counter() - start) / 1e6

    body = b"0" * UPLOAD_BYTES
    start = time.perf_counter()
    client.post(f"{base}/__up", content=body).raise_for_status()
    up = UPLOAD_BYTES * 8 / (time.perf_counter() - start) / 1e6
    return round(statistics.median(pings), 1), round(down, 1), round(up, 1)


def run_speedtest(session: Session, trigger: str) -> SpeedTest:
    test = SpeedTest(trigger=trigger)
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            test.ping_ms, test.down_mbps, test.up_mbps = measure_speed(
                client, get_settings().network_speedtest_url.rstrip("/")
            )
    except httpx.HTTPError as e:
        log.warning("Speed test failed: %s", e)
        test.error = f"Couldn't reach the speed test server ({type(e).__name__})."
    session.add(test)
    session.commit()
    session.refresh(test)
    return test


def speedtest_due(session: Session, now: datetime) -> bool:
    hours = get_settings().network_speedtest_hours
    if hours <= 0 or not state.up:
        return False
    latest = session.exec(select(SpeedTest).order_by(SpeedTest.at.desc())).first()
    return latest is None or _aware(latest.at) <= now - timedelta(hours=hours)


# --- Devices on the Wi-Fi -----------------------------------------------------------------


def import_scan(session: Session) -> Scan | None:
    """Reads the Pi's latest scan into the device list when the file has changed."""
    path = get_settings().network_scan_path
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return state.scan
    if mtime == state.scan_mtime:
        return state.scan
    try:
        scan = Scan.model_validate(json.loads(path.read_text()))
    except (OSError, ValueError, ValidationError) as e:
        log.warning("Couldn't read the network scan %s: %s", path, e)
        state.scan_mtime = mtime
        return state.scan
    seen_at = _aware(scan.generated_at)
    # The first scan is the starting point: what's there already is yours, so no alerts for it.
    baseline = session.exec(select(func.count()).select_from(NetworkDevice)).one() == 0
    for d in scan.devices:
        device = session.get(NetworkDevice, d.mac)
        if device is None:
            device = NetworkDevice(mac=d.mac, first_seen=seen_at, known=baseline or d.is_pi)
        elif _aware(device.last_seen) > seen_at:
            continue
        device.ip = d.ip
        device.hostname = d.hostname or device.hostname
        device.last_seen = seen_at
        device.is_pi = d.is_pi
        session.add(device)
    session.commit()
    state.scan_mtime = mtime
    state.scan = scan
    return scan


# --- The loop -----------------------------------------------------------------------------


def prune(session: Session, now: datetime) -> None:
    cutoff = now - KEEP
    for model, column in (
        (InternetHour, InternetHour.hour),
        (SpeedTest, SpeedTest.at),
        (Outage, Outage.started_at),
    ):
        for row in session.exec(select(model).where(column < cutoff)):
            session.delete(row)
    session.commit()


def tick() -> None:
    now = datetime.now(UTC)
    latency = probe()
    with Session(get_engine()) as session:
        record_probe(session, latency, now)
        import_scan(session)
        if speedtest_due(session, now) and speedtest_running.acquire(blocking=False):
            try:
                run_speedtest(session, "scheduled")
                prune(session, now)
            finally:
                speedtest_running.release()


async def loop() -> None:
    try:
        while True:
            try:
                await asyncio.to_thread(tick)
            except Exception:
                log.exception("Network monitor failed")
            await asyncio.sleep(TICK_SECONDS)
    finally:
        with Session(get_engine()) as session:
            flush(session)
