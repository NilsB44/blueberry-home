"""Earn apps: how the bandwidth-sharing apps on the Pi are doing.

The hub can't see systemd or Docker (it gets no access to them, on purpose), so this only reads
the JSON that scripts/pi-earn-status.py writes on the Pi every 5 minutes. Earnings live on each
app's own dashboard and aren't available here.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel, ValidationError

from app.auth.deps import OwnerUser
from app.config import get_settings

router = APIRouter(prefix="/api/earn", tags=["earn"])

STALE_AFTER = timedelta(minutes=20)


class App(BaseModel):
    installed: bool
    running: bool
    state: str
    # Why it isn't working although it may say "running", e.g. a refused login. Empty if fine.
    problem: str = ""
    today_bytes: int | None = None
    total_bytes: int | None = None
    counted_since: str | None = None
    log: list[str] = []


class Report(BaseModel):
    generated_at: datetime
    apps: dict[str, App]


class Status(BaseModel):
    # None until the Pi's timer has written its first report (bandwidth-sharing/setup.sh).
    generated_at: datetime | None = None
    stale: bool = True
    apps: dict[str, App] = {}
    error: str = ""


@router.get("")
def status(_: OwnerUser) -> Status:
    path = get_settings().earn_status_path
    if not path.exists():
        return Status()
    try:
        report = Report.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as e:
        return Status(error=f"The Pi's status file couldn't be read: {str(e)[:200]}")
    at = (
        report.generated_at
        if report.generated_at.tzinfo
        else report.generated_at.replace(tzinfo=UTC)
    )
    return Status(generated_at=at, stale=datetime.now(UTC) - at > STALE_AFTER, apps=report.apps)
