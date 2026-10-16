"""The weekly security check: looks over the hub's settings, who tried to get in, the Python
packages it runs on, and the report the Pi writes about itself (scripts/pi-security-check.py)."""

import ipaddress
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from importlib import metadata
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, func, select

from app.auth.models import User
from app.auth.network import is_public
from app.config import get_settings
from app.modules.security import tracker
from app.modules.security.models import AccessAttempt, SecurityReport
from app.modules.security.remote import away_setting, is_on

Status = Literal["ok", "warn", "fail", "unknown"]
# Worst first: a report's status is its worst check's.
SEVERITY: dict[str, int] = {"fail": 3, "warn": 2, "unknown": 1, "ok": 0}
WEEK = timedelta(days=7)
# The Pi's report is weekly; give it a day's grace before calling it stale.
HOST_REPORT_MAX_AGE = timedelta(days=8)
FAILED_LOGINS_WARN = 10


class Check(BaseModel):
    id: str = Field(max_length=64)
    group: Literal["hub", "pi"] = "hub"
    title: str = Field(max_length=120)
    status: Status
    summary: str = Field(max_length=500)
    details: list[str] = Field(default_factory=list, max_length=50)


class HostReport(BaseModel):
    generated_at: datetime
    hostname: str = Field(default="", max_length=64)
    checks: list[Check] = Field(max_length=50)


def worst(checks: list[Check]) -> Status:
    return max((c.status for c in checks), key=SEVERITY.__getitem__, default="ok")


def _day(d: date | datetime) -> str:
    return f"{d.day} {d:%b}"


def _since(days: int) -> date:
    return (datetime.now(UTC) - timedelta(days=days)).date()


def _attempts(session: Session, kind: str, days: int = 7) -> list[AccessAttempt]:
    return list(
        session.exec(
            select(AccessAttempt)
            .where(AccessAttempt.kind == kind, AccessAttempt.day >= _since(days))
            .order_by(AccessAttempt.count.desc())
        )
    )


def _by_ip(rows: list[AccessAttempt]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.ip] = counts.get(r.ip, 0) + r.count
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def check_network_ranges() -> Check:
    settings = get_settings()
    problems = []
    for spec in settings.trusted_networks:
        net = ipaddress.ip_network(spec, strict=False)
        if not (net.is_private or net.is_loopback or net.is_link_local):
            problems.append(f"{spec} is trusted without a login but isn't a home network range")
    cgnat = ipaddress.ip_network("100.64.0.0/10")
    ula = ipaddress.ip_network("fc00::/7")
    for spec in settings.away_networks:
        net = ipaddress.ip_network(spec, strict=False)
        inside = net.subnet_of(cgnat) if net.version == 4 else net.subnet_of(ula)
        if not inside:
            problems.append(f"{spec} is an away network but isn't a VPN range")
    if problems:
        return Check(
            id="network-ranges",
            title="Who counts as home",
            status="fail",
            summary="The hub trusts addresses outside your home and VPN. Fix HUB_TRUSTED_NETWORKS "
            "or HUB_AWAY_NETWORKS in .env.",
            details=problems,
        )
    return Check(
        id="network-ranges",
        title="Who counts as home",
        status="ok",
        summary="Only home network addresses get in without a login.",
        details=[f"Home: {', '.join(settings.trusted_networks)}"],
    )


def check_away_access(session: Session) -> Check:
    setting = away_setting(session)
    visits = _by_ip(_attempts(session, "away"))
    if not is_on(setting):
        return Check(
            id="away-access",
            title="Away access",
            status="ok",
            summary="Off: only devices on your home Wi-Fi can reach the hub. "
            f"{sum(visits.values())} requests came in from away this week.",
            details=[f"{ip}: {n} requests" for ip, n in list(visits.items())[:10]],
        )
    who = session.get(User, setting.changed_by) if setting.changed_by else None
    until = f", until {_day(setting.expires_at)}" if setting.expires_at else ""
    return Check(
        id="away-access",
        title="Away access",
        status="ok",
        summary=f"On since {_day(setting.changed_at)}{until}"
        f"{f' (turned on by {who.display_name})' if who else ''}: your devices on the VPN can "
        f"reach the hub. {sum(visits.values())} requests came in that way this week.",
        details=[f"{ip}: {n} requests" for ip, n in list(visits.items())[:10]],
    )


def check_refused(session: Session) -> Check:
    by_ip = _by_ip(_attempts(session, "blocked"))
    if not by_ip:
        return Check(
            id="refused",
            title="Refused visitors",
            status="ok",
            summary="Nothing outside your home network tried to reach the hub this week.",
        )
    details = [f"{ip}: {n} requests" for ip, n in list(by_ip.items())[:20]]
    public = [ip for ip in by_ip if is_public(ip)]
    if public:
        return Check(
            id="refused",
            title="Refused visitors",
            status="fail",
            summary=f"{len(public)} internet address(es) reached the Pi and were refused. "
            "Something is letting outside traffic in: check your router for port forwarding "
            "or UPnP, and that Tailscale Funnel is off.",
            details=details,
        )
    return Check(
        id="refused",
        title="Refused visitors",
        status="warn",
        summary=f"{sum(by_ip.values())} requests were refused from addresses that aren't "
        "home. Usually a VPN device while away access is off, or a guest network.",
        details=details,
    )


def check_failed_logins(session: Session) -> Check:
    rows = _attempts(session, "login")
    total = sum(r.count for r in rows)
    details = [f"{_day(r.day)} · {r.ip} tried @{r.detail}: {r.count}×" for r in rows[:20]]
    if total >= FAILED_LOGINS_WARN:
        return Check(
            id="failed-logins",
            title="Failed logins",
            status="warn",
            summary=f"{total} wrong passwords this week. If that wasn't someone at home "
            "forgetting theirs, look at which device it came from.",
            details=details,
        )
    return Check(
        id="failed-logins",
        title="Failed logins",
        status="ok",
        summary=f"{total} wrong password{'s' if total != 1 else ''} this week.",
        details=details,
    )


def check_people(session: Session) -> Check:
    week_ago = datetime.now(UTC) - WEEK
    new = list(session.exec(select(User).where(User.created_at >= week_ago).order_by(User.id)))
    admins = session.exec(select(func.count()).select_from(User).where(User.is_admin)).one()
    owners = list(session.exec(select(User).where(User.is_owner == True)))  # noqa: E712
    if len(owners) != 1:
        return Check(
            id="people",
            title="People and devices",
            status="fail",
            summary=f"The hub has {len(owners)} owners instead of one. Fix it on the Pi: "
            "docker compose exec api python -m app.owner <your username>.",
            details=[f"@{u.username}" for u in owners],
        )
    summary = f"Owned by {owners[0].display_name}. {admins} admin{'s' if admins != 1 else ''}. "
    summary += (
        f"{len(new)} new device{'s' if len(new) != 1 else ''} joined this week: check you "
        "recognise them."
        if new
        else "No new devices joined this week."
    )
    return Check(
        id="people",
        title="People and devices",
        status="ok",
        summary=summary,
        details=[
            f"{u.display_name} (@{u.username}){f' · {u.device}' if u.device else ''}"
            f"{' · admin' if u.is_admin else ''}"
            for u in new
        ],
    )


def check_cookies() -> Check:
    if get_settings().cookie_secure:
        return Check(
            id="cookies",
            title="Secure cookies",
            status="ok",
            summary="Login cookies are only ever sent over HTTPS.",
        )
    return Check(
        id="cookies",
        title="Secure cookies",
        status="warn",
        summary="HUB_COOKIE_SECURE is off, so login cookies also travel over plain HTTP. Fine "
        "for trying the hub on a laptop; turn it on for the Pi.",
    )


def _installed_packages() -> dict[str, str]:
    packages = {}
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if name and dist.version:
            packages[name.lower().replace("_", "-")] = dist.version
    return dict(sorted(packages.items()))


def query_osv(packages: dict[str, str]) -> dict[str, list[str]]:
    """Known vulnerability ids per package, from osv.dev. Raises httpx.HTTPError when offline."""
    queries = [
        {"package": {"name": n, "ecosystem": "PyPI"}, "version": v} for n, v in packages.items()
    ]
    resp = httpx.post(get_settings().osv_url, json={"queries": queries}, timeout=30)
    resp.raise_for_status()
    found = {}
    for (name, version), result in zip(packages.items(), resp.json()["results"], strict=True):
        ids = [v["id"] for v in result.get("vulns", [])]
        if ids:
            found[f"{name} {version}"] = ids
    return found


def check_dependencies(lookup: Callable[[dict[str, str]], dict[str, list[str]]]) -> Check:
    packages = _installed_packages()
    try:
        found = lookup(packages)
    except (httpx.HTTPError, KeyError, ValueError) as e:
        return Check(
            id="dependencies",
            title="Known vulnerabilities in the hub's packages",
            status="unknown",
            summary="Couldn't reach osv.dev to look them up. The hub needs an outgoing "
            "internet connection for this one check.",
            details=[str(e)[:200]],
        )
    if found:
        return Check(
            id="dependencies",
            title="Known vulnerabilities in the hub's packages",
            status="fail",
            summary=f"{len(found)} of the {len(packages)} Python packages the hub runs on have "
            "published vulnerabilities. Update the hub (git pull, docker compose build --pull, "
            "docker compose up -d); if that doesn't clear it, the fix isn't released yet.",
            details=[f"{p}: {', '.join(ids[:5])}" for p, ids in found.items()][:50],
        )
    return Check(
        id="dependencies",
        title="Known vulnerabilities in the hub's packages",
        status="ok",
        summary=f"None of the {len(packages)} Python packages have known vulnerabilities.",
    )


def check_host() -> list[Check]:
    path = get_settings().host_report_path
    setup = "Set up the Pi's weekly check: see docs/security.md."
    if not path.exists():
        return [
            Check(
                id="pi-report",
                group="pi",
                title="The Pi's own check",
                status="warn",
                summary=f"The Pi hasn't reported yet. {setup}",
            )
        ]
    try:
        report = HostReport.model_validate_json(path.read_bytes())
    except (OSError, ValidationError, json.JSONDecodeError) as e:
        return [
            Check(
                id="pi-report",
                group="pi",
                title="The Pi's own check",
                status="warn",
                summary="The Pi's report couldn't be read.",
                details=[str(e)[:300]],
            )
        ]
    generated = report.generated_at
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=UTC)
    age = datetime.now(UTC) - generated
    checks = [c.model_copy(update={"group": "pi"}) for c in report.checks]
    if age > HOST_REPORT_MAX_AGE:
        checks.insert(
            0,
            Check(
                id="pi-report",
                group="pi",
                title="The Pi's own check",
                status="warn",
                summary=f"The Pi last reported {age.days} days ago, so its timer may have "
                f"stopped. {setup}",
            ),
        )
    return checks


def run_checks(session: Session, lookup=None) -> list[Check]:
    tracker.flush(session)
    return [
        check_network_ranges(),
        check_away_access(session),
        check_refused(session),
        check_failed_logins(session),
        check_people(session),
        check_cookies(),
        check_dependencies(lookup or query_osv),
        *check_host(),
    ]


def run_report(session: Session, trigger: str, lookup=None) -> SecurityReport:
    report = SecurityReport(trigger=trigger)
    checks = run_checks(session, lookup)
    report.checks = json.dumps([c.model_dump() for c in checks])
    report.status = worst(checks)
    report.finished_at = datetime.now(UTC)
    session.add(report)
    session.commit()
    session.refresh(report)
    return report
