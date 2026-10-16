"""Runs the security check once a week and writes counted access attempts to the database.

The hub is a single process, so a background task is enough; no cron in the container."""

import asyncio
import logging
import threading
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_engine
from app.modules.security import tracker
from app.modules.security.checks import run_report
from app.modules.security.models import AccessAttempt, SecurityEvent, SecurityReport
from app.modules.security.remote import expire_away

log = logging.getLogger(__name__)

FLUSH_SECONDS = 60
KEEP_ATTEMPTS = timedelta(days=90)
KEEP_REPORTS = 52
KEEP_EVENTS = timedelta(days=365)

# One check at a time, whether scheduled or started from the Security page.
running = threading.Lock()


def last_slot(now: datetime) -> datetime:
    """The most recent scheduled time at or before now, in UTC."""
    settings = get_settings()
    local = now.astimezone(ZoneInfo(settings.timezone))
    slot = local.replace(hour=settings.security_check_hour, minute=0, second=0, microsecond=0)
    slot -= timedelta(days=(local.weekday() - settings.security_check_weekday) % 7)
    if slot > local:
        slot -= timedelta(days=7)
    return slot.astimezone(UTC)


def next_slot(now: datetime) -> datetime:
    return last_slot(now) + timedelta(days=7)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def due(session: Session, now: datetime) -> bool:
    latest = session.exec(
        select(SecurityReport)
        .where(SecurityReport.trigger == "scheduled")
        .order_by(SecurityReport.started_at.desc())
    ).first()
    # A Pi that was off at the scheduled time catches up when it starts.
    return latest is None or _aware(latest.started_at) < last_slot(now)


def prune(session: Session, now: datetime) -> None:
    for row in session.exec(
        select(AccessAttempt).where(AccessAttempt.day < (now - KEEP_ATTEMPTS).date())
    ):
        session.delete(row)
    old = session.exec(
        select(SecurityReport).order_by(SecurityReport.started_at.desc()).offset(KEEP_REPORTS)
    )
    for report in old:
        session.delete(report)
    for event in session.exec(select(SecurityEvent).where(SecurityEvent.at < now - KEEP_EVENTS)):
        session.delete(event)
    session.commit()


def tick() -> None:
    now = datetime.now(UTC)
    with Session(get_engine()) as session:
        tracker.flush(session)
        expire_away(session, now)
        if due(session, now) and running.acquire(blocking=False):
            try:
                report = run_report(session, "scheduled")
                log.info("Weekly security check finished: %s", report.status)
                prune(session, now)
            finally:
                running.release()


async def loop() -> None:
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            log.exception("Security check scheduler failed")
        await asyncio.sleep(FLUSH_SECONDS)
