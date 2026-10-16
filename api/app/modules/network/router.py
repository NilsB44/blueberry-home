from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth.deps import AdminUser, CurrentUser, DbSession
from app.modules.network import health, monitor
from app.modules.network.models import NetworkDevice, Outage, SpeedTest
from app.modules.security.models import AccessAttempt

router = APIRouter(prefix="/api/network", tags=["network"])

# The Pi scans every 5 minutes; a device missing from the latest scan is offline.
SCAN_STALE_AFTER = timedelta(minutes=20)


class Internet(BaseModel):
    # None until the first check, a minute after the hub starts.
    up: bool | None
    latency_ms: float | None
    checked_at: datetime | None
    down_since: datetime | None
    uptime_24h: float | None
    uptime_7d: float | None
    outages_7d: int


class SpeedOut(BaseModel):
    at: datetime
    trigger: str
    ping_ms: float | None
    down_mbps: float | None
    up_mbps: float | None
    error: str


class ScanInfo(BaseModel):
    at: datetime | None
    network: str
    gateway: str
    stale: bool
    online: int
    # Admins only: devices nobody has said they recognise yet.
    new_devices: int | None = None


class Overview(BaseModel):
    internet: Internet
    speed: SpeedOut | None
    health: health.Health
    scan: ScanInfo
    # Admins only: refused visits this week, from the Security page's log.
    refused_7d: int | None = None


class HourOut(BaseModel):
    hour: datetime
    uptime: float | None
    latency_ms: float | None
    latency_ms_max: float | None


class OutageOut(BaseModel):
    started_at: datetime
    ended_at: datetime | None
    minutes: float


class History(BaseModel):
    hours: list[HourOut]
    outages: list[OutageOut]
    speedtests: list[SpeedOut]


class DeviceOut(BaseModel):
    mac: str
    ip: str
    hostname: str
    name: str
    first_seen: datetime
    last_seen: datetime
    known: bool
    online: bool
    is_pi: bool
    is_gateway: bool
    # Phones and laptops make up a private MAC address per network; it can change after a reset.
    private_mac: bool


class DeviceChange(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    known: bool | None = None


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _speed_out(t: SpeedTest) -> SpeedOut:
    return SpeedOut(**t.model_dump(include=set(SpeedOut.model_fields)))


def _scan_at(scan: monitor.Scan | None) -> datetime | None:
    return _aware(scan.generated_at) if scan else None


def _online(device: NetworkDevice, scan_at: datetime | None, now: datetime) -> bool:
    if scan_at is None or now - scan_at > SCAN_STALE_AFTER:
        return False
    return _aware(device.last_seen) >= scan_at


def _private_mac(mac: str) -> bool:
    # The "locally administered" bit of the first byte.
    return bool(int(mac[:2], 16) & 0b10)


def _device_out(d: NetworkDevice, scan: monitor.Scan | None, now: datetime) -> DeviceOut:
    return DeviceOut(
        **d.model_dump(),
        online=_online(d, _scan_at(scan), now),
        is_gateway=bool(scan and scan.gateway and d.ip == scan.gateway),
        private_mac=_private_mac(d.mac),
    )


def _internet(db: Session, now: datetime) -> Internet:
    week = monitor.hours_since(db, now - timedelta(days=7))
    day = [h for h in week if _aware(h.hour) >= now - timedelta(hours=24)]
    outages = db.exec(select(Outage).where(Outage.started_at >= now - timedelta(days=7))).all()
    current = db.exec(select(Outage).where(Outage.ended_at.is_(None))).first()
    s = monitor.state
    return Internet(
        up=s.up,
        latency_ms=s.latency_ms,
        checked_at=s.checked_at,
        down_since=current.started_at if current and s.up is False else None,
        uptime_24h=monitor.uptime(day),
        uptime_7d=monitor.uptime(week),
        outages_7d=len(outages),
    )


@router.get("/overview")
def overview(user: CurrentUser, db: DbSession) -> Overview:
    now = datetime.now(UTC)
    scan = monitor.import_scan(db)
    scan_at = _scan_at(scan)
    devices = db.exec(select(NetworkDevice)).all()
    latest = db.exec(select(SpeedTest).order_by(SpeedTest.at.desc())).first()
    out = Overview(
        internet=_internet(db, now),
        speed=_speed_out(latest) if latest else None,
        health=health.read(),
        scan=ScanInfo(
            at=scan_at,
            network=scan.network if scan else "",
            gateway=scan.gateway if scan else "",
            stale=scan_at is None or now - scan_at > SCAN_STALE_AFTER,
            online=sum(_online(d, scan_at, now) for d in devices),
        ),
    )
    if user.is_admin:
        out.scan.new_devices = sum(not d.known for d in devices)
        week_ago = (now - timedelta(days=7)).date()
        out.refused_7d = sum(
            a.count
            for a in db.exec(
                select(AccessAttempt).where(
                    AccessAttempt.kind == "blocked", AccessAttempt.day >= week_ago
                )
            )
        )
    return out


@router.get("/history")
def history(_: CurrentUser, db: DbSession, days: int = 7) -> History:
    now = datetime.now(UTC)
    since = now - timedelta(days=min(max(days, 1), 90))
    hours = [
        HourOut(
            hour=h.hour,
            uptime=monitor.uptime([h]),
            latency_ms=round(h.latency_ms_total / (h.checks - h.failures), 1)
            if h.checks > h.failures
            else None,
            latency_ms_max=h.latency_ms_max or None,
        )
        for h in monitor.hours_since(db, since)
    ]
    outages = [
        OutageOut(
            started_at=o.started_at,
            ended_at=o.ended_at,
            minutes=round(
                ((_aware(o.ended_at) if o.ended_at else now) - _aware(o.started_at)).total_seconds()
                / 60,
                1,
            ),
        )
        for o in db.exec(
            select(Outage).where(Outage.started_at >= since).order_by(Outage.started_at.desc())
        )
    ]
    tests = db.exec(select(SpeedTest).where(SpeedTest.at >= since).order_by(SpeedTest.at.desc()))
    return History(hours=hours, outages=outages, speedtests=[_speed_out(t) for t in tests])


@router.post("/speedtest", status_code=status.HTTP_201_CREATED)
async def speedtest(_: AdminUser, db: DbSession) -> SpeedOut:
    if not monitor.speedtest_running.acquire(blocking=False):
        raise HTTPException(status.HTTP_409_CONFLICT, "A speed test is already running")
    try:
        test = await run_in_threadpool(monitor.run_speedtest, db, "manual")
    finally:
        monitor.speedtest_running.release()
    return _speed_out(test)


@router.get("/devices")
def devices(_: AdminUser, db: DbSession) -> list[DeviceOut]:
    now = datetime.now(UTC)
    scan = monitor.import_scan(db)
    rows = [_device_out(d, scan, now) for d in db.exec(select(NetworkDevice))]
    # New ones first, then who's online, then by address.
    return sorted(rows, key=lambda d: (d.known, not d.online, _ip_key(d.ip)))


def _ip_key(ip: str) -> tuple[int, ...]:
    parts = ip.split(".")
    return tuple(int(p) for p in parts) if all(p.isdigit() for p in parts) else (999,)


def _device(db: Session, mac: str) -> NetworkDevice:
    device = db.get(NetworkDevice, mac.lower())
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such device")
    return device


@router.patch("/devices/{mac}")
def change_device(mac: str, body: DeviceChange, _: AdminUser, db: DbSession) -> DeviceOut:
    device = _device(db, mac)
    if body.name is not None:
        device.name = body.name.strip()
    if body.known is not None:
        device.known = body.known
    db.add(device)
    db.commit()
    db.refresh(device)
    return _device_out(device, monitor.state.scan, datetime.now(UTC))


@router.post("/devices/acknowledge", status_code=status.HTTP_204_NO_CONTENT)
def acknowledge_all(_: AdminUser, db: DbSession) -> None:
    for device in db.exec(select(NetworkDevice).where(NetworkDevice.known == False)):  # noqa: E712
        device.known = True
        db.add(device)
    db.commit()


@router.delete("/devices/{mac}", status_code=status.HTTP_204_NO_CONTENT)
def forget_device(mac: str, _: AdminUser, db: DbSession) -> None:
    db.delete(_device(db, mac))
    db.commit()
