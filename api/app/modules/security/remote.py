"""Away access: whether your own devices on the VPN may reach the hub while you're out.

Off by default. Nothing is opened on the router either way: the VPN (Tailscale) makes an
outgoing connection from the Pi, and this switch decides whether the hub answers on it."""

from datetime import UTC, datetime

from sqlmodel import Session

from app.db import get_engine
from app.modules.security.models import HubSetting

AWAY_KEY = "away_access"


def away_setting(session: Session) -> HubSetting | None:
    return session.get(HubSetting, AWAY_KEY)


def away_enabled() -> bool:
    with Session(get_engine()) as session:
        setting = away_setting(session)
        return setting is not None and setting.value == "on"


def set_away(session: Session, enabled: bool, user_id: int | None) -> HubSetting:
    setting = away_setting(session) or HubSetting(key=AWAY_KEY)
    setting.value = "on" if enabled else "off"
    setting.changed_at = datetime.now(UTC)
    setting.changed_by = user_id
    session.add(setting)
    session.commit()
    session.refresh(setting)
    return setting
