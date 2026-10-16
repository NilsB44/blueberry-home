import json
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlmodel import select

from app.auth.deps import AdminUser, DbSession
from app.auth.models import User
from app.auth.network import is_away, is_public
from app.config import get_settings
from app.modules.security import scheduler, tracker
from app.modules.security.checks import Check, run_report
from app.modules.security.models import AccessAttempt, SecurityReport
from app.modules.security.remote import away_setting, set_away

router = APIRouter(prefix="/api/security", tags=["security"])


class AwayAccess(BaseModel):
    enabled: bool
    networks: list[str]
    changed_at: datetime | None = None
    changed_by: str | None = None
    # Turning it on only works from home; from away you can only turn it off.
    can_enable: bool


class AwayChange(BaseModel):
    enabled: bool


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
    return AwayAccess(
        enabled=setting is not None and setting.value == "on",
        networks=get_settings().away_networks,
        changed_at=setting.changed_at if setting else None,
        changed_by=who.display_name if who else None,
        can_enable=not is_away(request),
    )


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
def get_away(request: Request, _: AdminUser, db: DbSession) -> AwayAccess:
    return _away_out(db, request)


@router.put("/away")
def change_away(body: AwayChange, request: Request, user: AdminUser, db: DbSession) -> AwayAccess:
    if body.enabled and is_away(request):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Away access can only be turned on at home")
    set_away(db, body.enabled, user.id)
    return _away_out(db, request)


@router.get("/schedule")
def schedule(_: AdminUser, db: DbSession) -> Schedule:
    latest = db.exec(select(SecurityReport).order_by(SecurityReport.started_at.desc())).first()
    return Schedule(
        next_run_at=scheduler.next_slot(datetime.now(UTC)),
        latest=_report_out(latest) if latest else None,
    )


@router.get("/reports")
def list_reports(_: AdminUser, db: DbSession) -> list[ReportSummary]:
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
def get_report(report_id: int, _: AdminUser, db: DbSession) -> ReportOut:
    report = db.get(SecurityReport, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such report")
    return _report_out(report)


@router.post("/reports", status_code=status.HTTP_201_CREATED)
async def run_now(_: AdminUser, db: DbSession) -> ReportOut:
    if not scheduler.running.acquire(blocking=False):
        raise HTTPException(status.HTTP_409_CONFLICT, "A check is already running")
    try:
        report = await run_in_threadpool(run_report, db, "manual")
    finally:
        scheduler.running.release()
    return _report_out(report)


@router.get("/attempts")
def attempts(_: AdminUser, db: DbSession, days: int = 30) -> list[AttemptOut]:
    tracker.flush(db)
    since = (datetime.now(UTC) - timedelta(days=min(max(days, 1), 90))).date()
    rows = db.exec(
        select(AccessAttempt)
        .where(AccessAttempt.day >= since)
        .order_by(AccessAttempt.last_seen.desc())
        .limit(200)
    )
    return [AttemptOut(**r.model_dump(exclude={"id"}), from_internet=is_public(r.ip)) for r in rows]
