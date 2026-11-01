"""The trading watcher: reads index prices from IG's REST API, alerts your phone (through ntfy)
when a price comes near a level you typed in, and pings you when a new analysis is posted on the
feed you follow.

A background task in the hub's one process, like the network monitor: no cron needed. How often
it checks is set on the trading settings page, so it wakes every few seconds and asks itself
whether a check is due."""

import asyncio
import json
import logging
import threading
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_engine
from app.modules.security.models import HubSetting
from app.modules.trading.models import TradingAlert, TradingLevel

log = logging.getLogger(__name__)

SETTINGS_KEY = "trading"
SEEN_KEY = "trading_feed_seen"
WAKE_SECONDS = 5
KEEP_ALERTS = timedelta(days=365)
KEEP_SEEN = 300
MAX_FEED_BYTES = 2_000_000
LOGIN_RETRY = timedelta(minutes=15)
IG_LIVE = "https://api.ig.com/gateway/deal"
IG_DEMO = "https://demo-api.ig.com/gateway/deal"

_tick_lock = threading.Lock()


# --- Settings -----------------------------------------------------------------------------


class Instrument(BaseModel):
    name: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9 ._&-]+$")
    # IG's id for the market, e.g. "IX.D.DAX.IFD.IP". Found with the search on the settings page.
    epic: str = Field(default="", max_length=40, pattern=r"^[A-Za-z0-9._-]*$")
    # What one point is worth per contract, in the equity's currency. IG shows it on the market's
    # info page, e.g. Tyskland 40 Micro: "En punkt är värd EUR 1 (SEK 10.96)" means 10.96.
    point_value: float = Field(default=1, gt=0, le=1e6)


class TradingSettings(BaseModel):
    """Changed on the trading settings page; stored as JSON in HubSetting."""

    enabled: bool = False
    # IG allows 30 price requests a minute per account; one check is one request.
    price_check_seconds: int = Field(default=60, ge=15, le=3600)
    # Alert when the price is this many points from the entry zone, or inside it.
    near_points: float = Field(default=10, gt=0, le=10_000)
    # After an alert, the same level stays quiet this long.
    cooldown_minutes: int = Field(default=240, ge=1, le=10_080)
    equity: float = Field(default=250_000, gt=0, le=1e10)
    risk_pct: float = Field(default=1.0, gt=0, le=10)
    # An ntfy topic URL, e.g. https://ntfy.sh/some-long-random-name. Empty: alerts only in the hub.
    ntfy_url: str = Field(default="", max_length=200, pattern=r"^(https?://[^\s]+)?$")
    feed_enabled: bool = True
    feed_check_minutes: int = Field(default=30, ge=5, le=1440)
    feed_url: str = Field(
        default="https://mikrittrading.com/feed/", max_length=200, pattern=r"^(https?://[^\s]+)?$"
    )
    instruments: list[Instrument] = Field(
        default_factory=lambda: [
            Instrument(name=n) for n in ("DAX", "OMXS30", "Nasdaq 100", "S&P 500", "Gold")
        ],
        max_length=20,
    )

    @field_validator("instruments")
    @classmethod
    def _unique(cls, v: list[Instrument]) -> list[Instrument]:
        names = [i.name.lower() for i in v]
        if len(names) != len(set(names)):
            raise ValueError("Instrument names must be different")
        return v


def load_settings(session: Session) -> TradingSettings:
    row = session.get(HubSetting, SETTINGS_KEY)
    if row is None or not row.value:
        return TradingSettings()
    try:
        return TradingSettings.model_validate_json(row.value)
    except ValueError:
        log.warning("Trading settings are unreadable; using the defaults")
        return TradingSettings()


def save_settings(session: Session, settings: TradingSettings, user_id: int | None) -> None:
    row = session.get(HubSetting, SETTINGS_KEY) or HubSetting(key=SETTINGS_KEY)
    row.value = settings.model_dump_json()
    row.changed_at = datetime.now(UTC)
    row.changed_by = user_id
    session.add(row)
    session.commit()


# --- State --------------------------------------------------------------------------------


class Price(BaseModel):
    name: str
    epic: str
    bid: float | None
    offer: float | None
    # "TRADEABLE" while the market is open; alerts only fire then.
    status: str
    at: datetime

    @property
    def mid(self) -> float | None:
        if self.bid is None or self.offer is None:
            return None
        return round((self.bid + self.offer) / 2, 2)


class _State:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.prices: dict[str, Price] = {}
        self.price_checked_at: datetime | None = None
        self.price_error = ""
        self.feed_checked_at: datetime | None = None
        self.feed_error = ""
        self.cst: str | None = None
        self.security_token: str | None = None
        # After a failed login, wait before trying again: IG locks accounts that keep failing.
        self.login_retry_at: datetime | None = None


state = _State()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# --- Maths --------------------------------------------------------------------------------


def zone(level: TradingLevel) -> tuple[float, float]:
    return min(level.entry_low, level.entry_high), max(level.entry_low, level.entry_high)


def distance(level: TradingLevel, price: float) -> float:
    """Points from the price to the entry zone; 0 inside it."""
    low, high = zone(level)
    if low <= price <= high:
        return 0.0
    return round(min(abs(price - low), abs(price - high)), 2)


def entry_for(level: TradingLevel, price: float) -> float:
    """Where you'd get in: the point of the zone nearest the price."""
    low, high = zone(level)
    return min(max(price, low), high)


def bias(level: TradingLevel, price: float) -> str:
    """Contrarian: coming up from below is a short, coming down from above a long. Inside the
    zone, the edge the price is nearer is the side it came from."""
    low, high = zone(level)
    return "short" if price - low <= high - price else "long"


def stop_for(level: TradingLevel, side: str) -> float | None:
    if not level.stop_points:
        return None
    low, high = zone(level)
    return high + level.stop_points if side == "short" else low - level.stop_points


def point_value(settings: TradingSettings, instrument: str) -> float:
    return next((i.point_value for i in settings.instruments if i.name == instrument), 1)


def contracts(
    settings: TradingSettings, instrument: str, entry: float, stop: float
) -> float | None:
    """Contracts to trade so that being stopped out loses risk_pct of equity."""
    loss_per_contract = abs(entry - stop) * point_value(settings, instrument)
    if loss_per_contract == 0:
        return None
    return round(settings.equity * settings.risk_pct / 100 / loss_per_contract, 2)


def _fmt(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".")


def level_message(settings: TradingSettings, level: TradingLevel, price: float) -> str:
    entry = entry_for(level, price)
    low, high = zone(level)
    where = _fmt(low) if low == high else f"{_fmt(low)}–{_fmt(high)}"
    risk = settings.equity * settings.risk_pct / 100
    side = bias(level, price)
    stop = stop_for(level, side)
    size = contracts(settings, level.instrument, entry, stop) if stop is not None else None
    came = "from below" if side == "short" else "from above"
    lines = [f"{level.instrument} {_fmt(price)}, entry {where}, {came}."]
    if stop is None:
        lines.append(f"{side.capitalize()}.")
    else:
        lines.append(f"{side.capitalize()}, stop {_fmt(stop)} ({_fmt(abs(entry - stop))} pts).")
    if size is not None:
        lines.append(
            f"Size {_fmt(size)} contracts risks {_fmt(risk)} ({_fmt(settings.risk_pct)}% of "
            f"{_fmt(settings.equity)})."
        )
    if level.targets:
        lines.append(f"Targets {level.targets}.")
    if level.note:
        lines.append(level.note)
    return "\n".join(lines)


# --- IG -----------------------------------------------------------------------------------


IG_MISSING = "IG isn't set up: add HUB_IG_API_KEY, HUB_IG_USERNAME and HUB_IG_PASSWORD to .env"


class IgError(Exception):
    pass


def ig_configured() -> bool:
    s = get_settings()
    return bool(s.ig_api_key and s.ig_username and s.ig_password)


def make_client() -> httpx.Client:
    return httpx.Client(timeout=15, follow_redirects=False)


def _ig_base() -> str:
    return IG_DEMO if get_settings().ig_demo else IG_LIVE


def _ig_headers(version: str) -> dict[str, str]:
    return {
        "X-IG-API-KEY": get_settings().ig_api_key,
        "Version": version,
        "Accept": "application/json; charset=UTF-8",
        "Content-Type": "application/json; charset=UTF-8",
    }


def _ig_reason(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("errorCode", ""))[:100] or str(resp.status_code)
    except ValueError:
        return str(resp.status_code)


def _ig_login(client: httpx.Client) -> None:
    s = get_settings()
    now = datetime.now(UTC)
    if state.login_retry_at and now < state.login_retry_at:
        raise IgError("IG login failed recently; trying again in a few minutes")
    resp = client.post(
        f"{_ig_base()}/session",
        headers=_ig_headers("2"),
        json={"identifier": s.ig_username, "password": s.ig_password},
    )
    if resp.status_code != 200:
        state.login_retry_at = now + LOGIN_RETRY
        raise IgError(f"IG login failed: {_ig_reason(resp)}")
    state.login_retry_at = None
    state.cst = resp.headers.get("CST")
    state.security_token = resp.headers.get("X-SECURITY-TOKEN")
    if not state.cst or not state.security_token:
        raise IgError("IG login returned no session tokens")


def ig_get(client: httpx.Client, path: str, params: dict, version: str) -> dict:
    """GET from IG, logging in first and once more if the session has expired."""
    if not ig_configured():
        raise IgError(IG_MISSING)
    for attempt in range(2):
        if not state.cst:
            _ig_login(client)
        resp = client.get(
            f"{_ig_base()}{path}",
            params=params,
            headers={
                **_ig_headers(version),
                "CST": state.cst or "",
                "X-SECURITY-TOKEN": state.security_token or "",
            },
        )
        if resp.status_code == 401 and attempt == 0:
            state.cst = None
            continue
        if resp.status_code != 200:
            raise IgError(f"IG answered {_ig_reason(resp)} for {path}")
        return resp.json()
    raise IgError("IG session expired")


def fetch_prices(client: httpx.Client, instruments: list[Instrument]) -> dict[str, Price]:
    if not ig_configured():
        raise IgError(IG_MISSING)
    by_epic = {i.epic: i.name for i in instruments if i.epic}
    if not by_epic:
        raise IgError("No instrument has an IG market yet: pick them on the settings page")
    data = ig_get(
        client, "/markets", {"epics": ",".join(by_epic), "filter": "SNAPSHOT_ONLY"}, version="2"
    )
    now = datetime.now(UTC)
    prices = {}
    for m in data.get("marketDetails", []):
        epic = (m.get("instrument") or {}).get("epic")
        snap = m.get("snapshot") or {}
        if epic not in by_epic:
            continue
        name = by_epic[epic]
        prices[name] = Price(
            name=name,
            epic=epic,
            bid=snap.get("bid"),
            offer=snap.get("offer"),
            status=str(snap.get("marketStatus", "")),
            at=now,
        )
    # In the settings' order, whatever order IG answers in.
    return {i.name: prices[i.name] for i in instruments if i.name in prices}


def search_markets(client: httpx.Client, term: str) -> list[dict]:
    data = ig_get(client, "/markets", {"searchTerm": term}, version="1")
    return [
        {
            "epic": m.get("epic", ""),
            "name": m.get("instrumentName", ""),
            "type": m.get("instrumentType", ""),
            "expiry": m.get("expiry", ""),
            "bid": m.get("bid"),
            "offer": m.get("offer"),
        }
        for m in data.get("markets", [])[:20]
    ]


# --- Alerts -------------------------------------------------------------------------------


def send_alert(
    client: httpx.Client, session: Session, settings: TradingSettings, alert: TradingAlert
) -> TradingAlert:
    """Pushes the alert to ntfy (if set up) and keeps it in the history either way."""
    if not settings.ntfy_url:
        alert.error = "No ntfy topic set, so it's only here."
    else:
        headers = {"Title": alert.title.encode("ascii", "replace").decode(), "Tags": "chart"}
        if alert.kind == "level":
            headers["Priority"] = "high"
        if alert.link:
            headers["Click"] = alert.link
        try:
            client.post(
                settings.ntfy_url, content=alert.message.encode(), headers=headers
            ).raise_for_status()
            alert.delivered = True
        except httpx.HTTPError as e:
            log.warning("Couldn't send a trading alert: %s", e)
            alert.error = f"Couldn't reach ntfy ({type(e).__name__})."
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


def _today() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def check_levels(
    client: httpx.Client,
    session: Session,
    settings: TradingSettings,
    prices: dict[str, Price],
    now: datetime,
) -> list[TradingAlert]:
    today = _today()
    cooldown = timedelta(minutes=settings.cooldown_minutes)
    sent = []
    for level in session.exec(select(TradingLevel).where(TradingLevel.active)).all():
        price = prices.get(level.instrument)
        if price is None or price.mid is None or price.status != "TRADEABLE":
            continue
        if level.valid_until and level.valid_until < today:
            continue
        if level.last_alert_at and now - _aware(level.last_alert_at) < cooldown:
            continue
        if distance(level, price.mid) > settings.near_points:
            continue
        level.last_alert_at = now
        session.add(level)
        alert = TradingAlert(
            at=now,
            kind="level",
            level_id=level.id,
            instrument=level.instrument,
            price=price.mid,
            title=f"{level.instrument} {bias(level, price.mid)} level near",
            message=level_message(settings, level, price.mid),
        )
        sent.append(send_alert(client, session, settings, alert))
    return sent


# --- Feed ---------------------------------------------------------------------------------


class Post(BaseModel):
    id: str
    title: str
    link: str
    premium: bool


def parse_feed(xml: bytes) -> list[Post]:
    root = ET.fromstring(xml)
    posts = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        post_id = (item.findtext("guid") or link).strip()
        if not post_id:
            continue
        categories = [(c.text or "").lower() for c in item.findall("category")]
        posts.append(
            Post(
                id=post_id[:300],
                title=(item.findtext("title") or "").strip()[:100],
                link=link[:300] if link.startswith(("https://", "http://")) else "",
                premium=any("premium" in c for c in categories),
            )
        )
    return posts


def check_feed(
    client: httpx.Client, session: Session, settings: TradingSettings
) -> list[TradingAlert]:
    """Alerts for posts not seen before. The first read only remembers what's there."""
    resp = client.get(settings.feed_url, follow_redirects=True)
    resp.raise_for_status()
    if len(resp.content) > MAX_FEED_BYTES:
        raise ValueError("The feed is too large")
    posts = parse_feed(resp.content)
    row = session.get(HubSetting, SEEN_KEY)
    seen = json.loads(row.value) if row and row.value else None
    sent = []
    if seen is not None:
        for post in reversed([p for p in posts if p.id not in seen]):
            alert = TradingAlert(
                kind="post",
                title="New premium analysis" if post.premium else "New analysis",
                message=post.title or post.link,
                link=post.link,
            )
            sent.append(send_alert(client, session, settings, alert))
    ids = [p.id for p in posts] + [i for i in (seen or []) if i not in {p.id for p in posts}]
    row = row or HubSetting(key=SEEN_KEY)
    row.value = json.dumps(ids[:KEEP_SEEN])
    row.changed_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    return sent


# --- The loop -----------------------------------------------------------------------------


def _due(last: datetime | None, every: timedelta, now: datetime) -> bool:
    return last is None or now - last >= every


def tick(force: bool = False) -> None:
    """One look at prices and the feed when they're due, or right away when forced."""
    with _tick_lock, Session(get_engine()) as session:
        settings = load_settings(session)
        if not (settings.enabled or force):
            return
        with make_client() as client:
            _check(client, session, settings, force)


def _check(client: httpx.Client, session: Session, settings: TradingSettings, force: bool) -> None:
    now = datetime.now(UTC)
    every = timedelta(seconds=settings.price_check_seconds)
    if force or _due(state.price_checked_at, every, now):
        state.price_checked_at = now
        try:
            state.prices = fetch_prices(client, settings.instruments)
            state.price_error = ""
            check_levels(client, session, settings, state.prices, now)
        except (IgError, httpx.HTTPError, ValueError) as e:
            log.warning("Price check failed: %s", e)
            state.price_error = (
                str(e) if isinstance(e, IgError) else f"Couldn't reach IG ({type(e).__name__})."
            )
    every = timedelta(minutes=settings.feed_check_minutes)
    if settings.feed_enabled and (force or _due(state.feed_checked_at, every, now)):
        state.feed_checked_at = now
        try:
            check_feed(client, session, settings)
            state.feed_error = ""
        except (httpx.HTTPError, ET.ParseError, ValueError) as e:
            log.warning("Feed check failed: %s", e)
            state.feed_error = f"Couldn't read the feed ({type(e).__name__})."
        prune(session, now)


def prune(session: Session, now: datetime) -> None:
    for alert in session.exec(select(TradingAlert).where(TradingAlert.at < now - KEEP_ALERTS)):
        session.delete(alert)
    session.commit()


async def loop() -> None:
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            log.exception("Trading watcher failed")
        await asyncio.sleep(WAKE_SECONDS)
