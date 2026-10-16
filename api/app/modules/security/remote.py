"""Away access: whether your own devices on the VPN may reach the hub while you're out.

Off by default, and when it's on it switches itself off again after a time limit the owner
picks. Nothing is opened on the router either way: the VPN (Tailscale) makes an outgoing
connection from the Pi, and this switch decides whether the hub answers on it."""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from app.db import get_engine
from app.modules.security.events import log_event
from app.modules.security.models import HubSetting

AWAY_KEY = "away_access"
# How long away access may stay on, in hours: from an afternoon out to a month's travel.
AWAY_DURATIONS = (4, 24, 72, 168, 720)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def away_setting(session: Session) -> HubSetting | None:
    return session.get(HubSetting, AWAY_KEY)


def is_on(setting: HubSetting | None, now: datetime | None = None) -> bool:
    if setting is None or setting.value != "on":
        return False
    now = now or datetime.now(UTC)
    return setting.expires_at is None or _aware(setting.expires_at) > now


def away_enabled() -> bool:
    with Session(get_engine()) as session:
        return is_on(away_setting(session))


def set_away(
    session: Session,
    enabled: bool,
    user_id: int | None,
    hours: int | None = None,
    ip: str | None = None,
) -> HubSetting:
    now = datetime.now(UTC)
    setting = away_setting(session) or HubSetting(key=AWAY_KEY)
    setting.value = "on" if enabled else "off"
    setting.changed_at = now
    setting.changed_by = user_id
    setting.expires_at = now + timedelta(hours=hours or 24) if enabled else None
    session.add(setting)
    session.commit()
    session.refresh(setting)
    if enabled:
        log_event(session, "away-on", f"for {hours or 24} hours", user_id, ip)
    else:
        log_event(session, "away-off", "", user_id, ip)
    return setting


def expire_away(session: Session, now: datetime) -> bool:
    """Record that away access ran out, so the page and log say so. True if it just did."""
    setting = away_setting(session)
    if setting is None or setting.value != "on" or is_on(setting, now):
        return False
    setting.value = "off"
    setting.changed_at = now
    setting.changed_by = None
    session.add(setting)
    session.commit()
    log_event(session, "away-expired", "time limit reached")
    return True
