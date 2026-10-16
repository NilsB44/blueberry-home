import json
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, field_validator
from sqlmodel import select

from app.auth.deps import COOKIE_NAME, DbSession, OwnerUser
from app.auth.models import AuthSession, User
from app.auth.network import is_away, is_public
from app.auth.security import hash_token
from app.config import get_settings
from app.modules.security import scheduler, tracker
from app.modules.security.checks import Check, run_report
from app.modules.security.events import log_event
from app.modules.security.models import AccessAttempt, SecurityEvent, SecurityReport
from app.modules.security.remote import AWAY_DURATIONS, away_setting, is_on, set_away

router = APIRouter(prefix="/api/security", tags=["security"])


class AwayAccess(BaseModel):
    enabled: bool
    networks: list[str]
    changed_at: datetime | None = None
    changed_by: str | None = None
    expires_at: datetime | None = None
    durations: list[int] = list(AWAY_DURATIONS)
    # Turning it on only works from home; from away you can only turn it off.
    can_enable: bool


class AwayChange(BaseModel):
    enabled: bool
    # How many hours to stay on; one of AWAY_DURATIONS.
    hours: int = 24

    @field_validator("hours")
    @classmethod
    def _known_duration(cls, hours: int) -> int:
        if hours not in AWAY_DURATIONS:
            raise ValueError(f"hours must be one of {AWAY_DURATIONS}")
        return hours


class EventOut(BaseModel):
    at: datetime
    action: str
    detail: str
    who: str | None
    ip: str | None


class DeviceSession(BaseModel):
    id: str
    user: str
    username: str
    device: str | None
    is_owner: bool
    signed_in_at: datetime
    last_seen_at: datetime | None
    last_ip: str | None
    this_device: bool


class ReportOut(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None
    trigger: str
    status: str
    checks: list[Check]


class ReportSummary(BaseModel):
    id: int
    started_at: datetime
    trigger: str
    status: str
    counts: dict[str, int]


class Schedule(BaseModel):
    next_run_at: datetime
    latest: ReportOut | None


class AttemptOut(BaseModel):
    kind: str
    ip: str
    day: date
    count: int
    detail: str
    last_seen: datetime
    from_internet: bool


def _away_out(db: DbSession, request: Request) -> AwayAccess:
    setting = away_setting(db)
    who = db.get(User, setting.changed_by) if setting and setting.changed_by else None
    on = is_on(setting)
    return AwayAccess(
        enabled=on,
        networks=get_settings().away_networks,
        changed_at=setting.changed_at if setting else None,
        changed_by=who.display_name if who else None,
        expires_at=setting.expires_at if on and setting else None,
        can_enable=not is_away(request),
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _report_out(report: SecurityReport) -> ReportOut:
    return ReportOut(
        id=report.id,
        started_at=report.started_at,
        finished_at=report.finished_at,
        trigger=report.trigger,
        status=report.status,
        checks=[Check.model_validate(c) for c in json.loads(report.checks)],
    )


@router.get("/away")
def get_away(request: Request, _: OwnerUser, db: DbSession) -> AwayAccess:
    return _away_out(db, request)


@router.put("/away")
def change_away(body: AwayChange, request: Request, user: OwnerUser, db: DbSession) -> AwayAccess:
    if body.enabled and is_away(request):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Away access can only be turned on at home")
    set_away(db, body.enabled, user.id, body.hours, _ip(request))
    return _away_out(db, request)


@router.get("/schedule")
def schedule(_: OwnerUser, db: DbSession) -> Schedule:
    latest = db.exec(select(SecurityReport).order_by(SecurityReport.started_at.desc())).first()
    return Schedule(
        next_run_at=scheduler.next_slot(datetime.now(UTC)),
        latest=_report_out(latest) if latest else None,
    )


@router.get("/reports")
def list_reports(_: OwnerUser, db: DbSession) -> list[ReportSummary]:
    reports = db.exec(select(SecurityReport).order_by(SecurityReport.started_at.desc()).limit(12))
    out = []
    for r in reports:
        counts: dict[str, int] = {}
        for c in json.loads(r.checks):
            counts[c["status"]] = counts.get(c["status"], 0) + 1
        out.append(
            ReportSummary(
                id=r.id, started_at=r.started_at, trigger=r.trigger, status=r.status, counts=counts
            )
        )
    return out


@router.get("/reports/{report_id}")
def get_report(report_id: int, _: OwnerUser, db: DbSession) -> ReportOut:
    report = db.get(SecurityReport, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such report")
    return _report_out(report)


@router.post("/reports", status_code=status.HTTP_201_CREATED)
async def run_now(request: Request, user: OwnerUser, db: DbSession) -> ReportOut:
    if not scheduler.running.acquire(blocking=False):
        raise HTTPException(status.HTTP_409_CONFLICT, "A check is already running")
    try:
        report = await run_in_threadpool(run_report, db, "manual")
    finally:
        scheduler.running.release()
    log_event(db, "check", f"run by hand: {report.status}", user.id, _ip(request))
    return _report_out(report)


@router.get("/attempts")
def attempts(_: OwnerUser, db: DbSession, days: int = 30) -> list[AttemptOut]:
    tracker.flush(db)
    since = (datetime.now(UTC) - timedelta(days=min(max(days, 1), 90))).date()
    rows = db.exec(
        select(AccessAttempt)
        .where(AccessAttempt.day >= since)
        .order_by(AccessAttempt.last_seen.desc())
        .limit(200)
    )
    return [AttemptOut(**r.model_dump(exclude={"id"}), from_internet=is_public(r.ip)) for r in rows]


@router.get("/events")
def events(_: OwnerUser, db: DbSession) -> list[EventOut]:
    rows = db.exec(select(SecurityEvent).order_by(SecurityEvent.at.desc()).limit(100))
    names = {u.id: u.display_name for u in db.exec(select(User))}
    return [
        EventOut(at=e.at, action=e.action, detail=e.detail, who=names.get(e.user_id), ip=e.ip)
        for e in rows
    ]


@router.get("/sessions")
def sessions(
    _: OwnerUser,
    db: DbSession,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> list[DeviceSession]:
    now = datetime.now(UTC)
    mine = hash_token(token) if token else None
    users = {u.id: u for u in db.exec(select(User))}
    out = []
    for s in db.exec(select(AuthSession).order_by(AuthSession.created_at.desc())):
        user = users.get(s.user_id)
        expires = s.expires_at if s.expires_at.tzinfo else s.expires_at.replace(tzinfo=UTC)
        if user is None or expires < now:
            continue
        out.append(
            DeviceSession(
                id=s.token_hash,
                user=user.display_name,
                username=user.username,
                device=user.device,
                is_owner=bool(user.is_owner),
                signed_in_at=s.created_at,
                last_seen_at=s.last_seen_at,
                last_ip=s.last_ip,
                this_device=s.token_hash == mine,
            )
        )
    return out


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(
    session_id: str,
    request: Request,
    owner: OwnerUser,
    db: DbSession,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> None:
    """Sign a device out. On the home Wi-Fi it can join again as a new person, but it loses
    who it was, and away it can't get back in at all."""
    session = db.get(AuthSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such session")
    if token and session_id == hash_token(token):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That's this device")
    user = db.get(User, session.user_id)
    db.delete(session)
    db.commit()
    log_event(
        db,
        "signed-out",
        f"{user.display_name if user else 'someone'} (@{user.username if user else '?'})",
        owner.id,
        _ip(request),
    )
