"""How much Claude is being used: Claude Code on the Pi (from its logs) and, optionally, API
keys (from the Admin API). A Claude plan's remaining allowance isn't available from any API,
so the page links to claude.ai for that."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.auth.deps import OwnerUser
from app.config import get_settings
from app.modules.claude import admin_api
from app.modules.claude.claude_code import Reply, read_replies
from app.modules.claude.pricing import cost_usd

router = APIRouter(prefix="/api/claude", tags=["claude"])

PLAN_USAGE_URL = "https://claude.ai/settings/usage"
DAYS = 30


class Day(BaseModel):
    day: date
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    tokens: int = 0
    cost_usd: float = 0.0


class Share(BaseModel):
    name: str
    tokens: int
    cost_usd: float | None
    replies: int


class CodeUsage(BaseModel):
    found: bool
    days: list[Day]
    models: list[Share]
    projects: list[Share]
    today_tokens: int
    avg_tokens_7d: int
    avg_tokens_30d: int
    tokens_30d: int
    cost_30d: float
    avg_cost_7d: float
    month_estimate: float
    sessions_30d: int
    cache_hit_rate: float | None
    unpriced_models: list[str]


class ApiUsage(BaseModel):
    configured: bool
    error: str | None = None
    days: list[Day] = []
    models: list[Share] = []
    cost_30d: float = 0.0
    avg_cost_7d: float = 0.0


class Usage(BaseModel):
    plan_usage_url: str
    code: CodeUsage
    api: ApiUsage


def _reply_tokens(r: Reply) -> int:
    return r.input + r.output + r.cache_read + r.cache_write_5m + r.cache_write_1h


def _reply_cost(r: Reply) -> float | None:
    return cost_usd(r.model, r.input, r.output, r.cache_read, r.cache_write_5m, r.cache_write_1h)


def _shares(groups: dict[str, list[Reply]]) -> list[Share]:
    out = []
    for name, replies in groups.items():
        costs = [_reply_cost(r) for r in replies]
        out.append(
            Share(
                name=name,
                tokens=sum(_reply_tokens(r) for r in replies),
                cost_usd=None if any(c is None for c in costs) else round(sum(costs), 2),
                replies=len(replies),
            )
        )
    return sorted(out, key=lambda s: -s.tokens)


def code_usage(today: date) -> CodeUsage:
    settings = get_settings()
    root = settings.claude_logs_dir
    first = today - timedelta(days=DAYS - 1)
    replies = [
        r for r in read_replies(root, ZoneInfo(settings.timezone)) if first <= r.day <= today
    ]
    days = {first + timedelta(days=i): Day(day=first + timedelta(days=i)) for i in range(DAYS)}
    by_model: dict[str, list[Reply]] = defaultdict(list)
    by_project: dict[str, list[Reply]] = defaultdict(list)
    for r in replies:
        d = days[r.day]
        d.input += r.input
        d.output += r.output
        d.cache_read += r.cache_read
        d.cache_write += r.cache_write_5m + r.cache_write_1h
        d.tokens += _reply_tokens(r)
        d.cost_usd += _reply_cost(r) or 0.0
        by_model[r.model].append(r)
        by_project[r.project].append(r)
    day_list = list(days.values())
    for d in day_list:
        d.cost_usd = round(d.cost_usd, 2)
    last7 = day_list[-7:]
    total = sum(d.tokens for d in day_list)
    cost30 = sum(d.cost_usd for d in day_list)
    avg_cost_7d = sum(d.cost_usd for d in last7) / 7
    cached = sum(d.cache_read for d in day_list)
    fresh_input = sum(d.input + d.cache_write for d in day_list)
    return CodeUsage(
        found=root.is_dir() and any(root.rglob("*.jsonl")),
        days=day_list,
        models=_shares(by_model),
        projects=_shares(by_project)[:10],
        today_tokens=day_list[-1].tokens,
        avg_tokens_7d=sum(d.tokens for d in last7) // 7,
        avg_tokens_30d=total // DAYS,
        tokens_30d=total,
        cost_30d=round(cost30, 2),
        avg_cost_7d=round(avg_cost_7d, 2),
        month_estimate=round(avg_cost_7d * 30, 2),
        sessions_30d=len({r.session for r in replies if r.session}),
        cache_hit_rate=round(cached / (cached + fresh_input), 3) if cached + fresh_input else None,
        unpriced_models=sorted({r.model for r in replies if _reply_cost(r) is None}),
    )


def api_usage() -> ApiUsage:
    if not get_settings().anthropic_admin_key:
        return ApiUsage(configured=False)
    try:
        data = admin_api.cached_fetch()
    except httpx.HTTPStatusError as e:
        reason = {401: "the admin key was rejected", 403: "the key isn't an Admin API key"}
        return ApiUsage(
            configured=True,
            error=f"Anthropic said no ({e.response.status_code}): "
            f"{reason.get(e.response.status_code, 'see the hub log')}.",
        )
    except (httpx.HTTPError, KeyError, ValueError):
        return ApiUsage(configured=True, error="Couldn't reach api.anthropic.com.")
    days = [
        Day(day=date.fromisoformat(d["day"]), tokens=d["tokens"], cost_usd=round(d["cost_usd"], 2))
        for d in data["days"]
    ]
    models = [
        Share(name=m, tokens=t, cost_usd=None, replies=0)
        for m, t in sorted(data["models"].items(), key=lambda kv: -kv[1])
    ]
    return ApiUsage(
        configured=True,
        days=days,
        models=models,
        cost_30d=round(sum(d.cost_usd for d in days), 2),
        avg_cost_7d=round(sum(d.cost_usd for d in days[-7:]) / 7, 2),
    )


@router.get("/usage")
async def usage(_: OwnerUser) -> Usage:
    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    code = await run_in_threadpool(code_usage, today)
    api = await run_in_threadpool(api_usage)
    return Usage(plan_usage_url=PLAN_USAGE_URL, code=code, api=api)
