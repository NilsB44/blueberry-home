from datetime import date, datetime
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session, select

from app.auth.deps import DbSession, OwnerUser
from app.config import get_settings
from app.modules.trading import watcher
from app.modules.trading.models import TradingAlert, TradingLevel
from app.modules.trading.watcher import TradingSettings

router = APIRouter(prefix="/api/trading", tags=["trading"])


class PriceOut(BaseModel):
    name: str
    epic: str
    bid: float | None
    offer: float | None
    mid: float | None
    status: str
    at: datetime


class Status(BaseModel):
    ig_configured: bool
    ig_demo: bool
    enabled: bool
    price_checked_at: datetime | None
    price_error: str
    feed_checked_at: datetime | None
    feed_error: str
    prices: list[PriceOut]


class LevelIn(BaseModel):
    instrument: str = Field(min_length=1, max_length=20)
    bias: Literal["long", "short"]
    entry_low: float
    # Leave out for a single price level.
    entry_high: float | None = None
    stop: float
    targets: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=300)
    valid_until: date | None = None

    def zone(self) -> tuple[float, float]:
        other = self.entry_low if self.entry_high is None else self.entry_high
        return min(self.entry_low, other), max(self.entry_low, other)

    @model_validator(mode="after")
    def _stop_on_the_right_side(self) -> "LevelIn":
        low, high = self.zone()
        if self.bias == "long" and self.stop >= low:
            raise ValueError("A long's stop goes below the entry")
        if self.bias == "short" and self.stop <= high:
            raise ValueError("A short's stop goes above the entry")
        return self


class LevelChange(BaseModel):
    active: bool


class LevelOut(BaseModel):
    id: int
    created_at: datetime
    instrument: str
    bias: str
    entry_low: float
    entry_high: float
    stop: float
    targets: str
    note: str
    valid_until: date | None
    active: bool
    last_alert_at: datetime | None
    # From the latest price, when there is one.
    price: float | None
    distance: float | None
    # Stake per point that risks the set share of equity, entering at the zone.
    size_per_point: float | None


class AlertOut(BaseModel):
    id: int
    at: datetime
    kind: str
    level_id: int | None
    instrument: str
    price: float | None
    title: str
    message: str
    link: str
    delivered: bool
    error: str


class MarketOut(BaseModel):
    epic: str
    name: str
    type: str
    expiry: str
    bid: float | None
    offer: float | None


def _status(enabled: bool) -> Status:
    s = watcher.state
    return Status(
        ig_configured=watcher.ig_configured(),
        ig_demo=get_settings().ig_demo,
        enabled=enabled,
        price_checked_at=s.price_checked_at,
        price_error=s.price_error,
        feed_checked_at=s.feed_checked_at,
        feed_error=s.feed_error,
        prices=[PriceOut(**p.model_dump(), mid=p.mid) for p in s.prices.values()],
    )


def _level_out(level: TradingLevel, settings: TradingSettings) -> LevelOut:
    p = watcher.state.prices.get(level.instrument)
    price = p.mid if p else None
    entry = watcher.entry_for(level, price)
    return LevelOut(
        **level.model_dump(),
        price=price,
        distance=watcher.distance(level, price) if price is not None else None,
        size_per_point=watcher.size_per_point(settings, entry, level.stop),
    )


@router.get("/settings")
def get_trading_settings(_: OwnerUser, db: DbSession) -> TradingSettings:
    return watcher.load_settings(db)


@router.put("/settings")
def put_trading_settings(body: TradingSettings, user: OwnerUser, db: DbSession) -> TradingSettings:
    watcher.save_settings(db, body, user.id)
    return body


@router.get("/status")
def get_status(_: OwnerUser, db: DbSession) -> Status:
    return _status(watcher.load_settings(db).enabled)


@router.post("/check")
async def check_now(_: OwnerUser, db: DbSession) -> Status:
    """Reads prices and the feed right away, even while the watcher is switched off."""
    await run_in_threadpool(watcher.tick, True)
    return _status(watcher.load_settings(db).enabled)


@router.post("/test-alert")
def test_alert(_: OwnerUser, db: DbSession) -> AlertOut:
    settings = watcher.load_settings(db)
    alert = TradingAlert(
        kind="test", title="Test alert", message="Alerts from the hub reach this phone."
    )
    with watcher.make_client() as client:
        alert = watcher.send_alert(client, db, settings, alert)
    return AlertOut(**alert.model_dump())


@router.get("/markets")
def search_markets(_: OwnerUser, q: str = Query(min_length=2, max_length=40)) -> list[MarketOut]:
    """Finds IG's id (epic) for a market, e.g. "Germany 40"."""
    try:
        with watcher.make_client() as client:
            return [MarketOut(**m) for m in watcher.search_markets(client, q)]
    except watcher.IgError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    except (httpx.HTTPError, ValueError) as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't reach IG") from e


@router.get("/levels")
def list_levels(_: OwnerUser, db: DbSession) -> list[LevelOut]:
    settings = watcher.load_settings(db)
    levels = db.exec(
        select(TradingLevel).order_by(TradingLevel.active.desc(), TradingLevel.created_at.desc())
    ).all()
    return [_level_out(lv, settings) for lv in levels]


@router.post("/levels", status_code=status.HTTP_201_CREATED)
def create_level(body: LevelIn, _: OwnerUser, db: DbSession) -> LevelOut:
    settings = watcher.load_settings(db)
    if body.instrument not in {i.name for i in settings.instruments}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown instrument")
    low, high = body.zone()
    level = TradingLevel(
        **body.model_dump(exclude={"entry_low", "entry_high"}), entry_low=low, entry_high=high
    )
    db.add(level)
    db.commit()
    db.refresh(level)
    return _level_out(level, settings)


def _level(db: Session, level_id: int) -> TradingLevel:
    level = db.get(TradingLevel, level_id)
    if level is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such level")
    return level


@router.patch("/levels/{level_id}")
def change_level(level_id: int, body: LevelChange, _: OwnerUser, db: DbSession) -> LevelOut:
    level = _level(db, level_id)
    level.active = body.active
    if body.active:
        level.last_alert_at = None
    db.add(level)
    db.commit()
    db.refresh(level)
    return _level_out(level, watcher.load_settings(db))


@router.delete("/levels/{level_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_level(level_id: int, _: OwnerUser, db: DbSession) -> None:
    db.delete(_level(db, level_id))
    db.commit()


@router.get("/alerts")
def list_alerts(_: OwnerUser, db: DbSession) -> list[AlertOut]:
    alerts = db.exec(select(TradingAlert).order_by(TradingAlert.at.desc()).limit(100)).all()
    return [AlertOut(**a.model_dump()) for a in alerts]
