"""Spend on Anthropic API keys, from the Usage and Cost Admin API (console orgs only; it needs
an Admin API key, sk-ant-admin..., in HUB_ANTHROPIC_ADMIN_KEY). Raw HTTP: these report
endpoints aren't in the SDKs. Results are cached so the page doesn't poll the API."""

import threading
import time
from datetime import UTC, datetime, timedelta

import httpx

from app.config import get_settings

BASE = "https://api.anthropic.com/v1/organizations"
CACHE_SECONDS = 600

_lock = threading.Lock()
_cached: tuple[float, dict] | None = None


def _get_all(client: httpx.Client, path: str, params: dict) -> list[dict]:
    buckets, page = [], None
    for _ in range(10):
        resp = client.get(f"{BASE}/{path}", params={**params, **({"page": page} if page else {})})
        resp.raise_for_status()
        body = resp.json()
        buckets += body.get("data", [])
        if not body.get("has_more"):
            break
        page = body.get("next_page")
    return buckets


def fetch(days: int = 30) -> dict:
    """{"days": [{"day", "tokens", "cost_usd"}], "models": {model: tokens}}."""
    key = get_settings().anthropic_admin_key
    end = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    start = end - timedelta(days=days)
    params = {
        "starting_at": start.isoformat().replace("+00:00", "Z"),
        "ending_at": end.isoformat().replace("+00:00", "Z"),
        "bucket_width": "1d",
        "limit": 31,
    }
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "user-agent": "BlueberryHome/0.1",
    }
    with httpx.Client(headers=headers, timeout=20) as client:
        usage = _get_all(client, "usage_report/messages", {**params, "group_by[]": "model"})
        costs = _get_all(
            client, "cost_report", {k: v for k, v in params.items() if k != "bucket_width"}
        )

    per_day: dict[str, dict] = {}
    models: dict[str, int] = {}
    for bucket in usage:
        day = bucket["starting_at"][:10]
        row = per_day.setdefault(day, {"day": day, "tokens": 0, "cost_usd": 0.0})
        for r in bucket.get("results", []):
            cache = r.get("cache_creation") or {}
            tokens = (
                r.get("uncached_input_tokens", 0)
                + r.get("cache_read_input_tokens", 0)
                + cache.get("ephemeral_5m_input_tokens", 0)
                + cache.get("ephemeral_1h_input_tokens", 0)
                + r.get("output_tokens", 0)
            )
            row["tokens"] += tokens
            model = r.get("model") or "other"
            models[model] = models.get(model, 0) + tokens
    for bucket in costs:
        day = bucket["starting_at"][:10]
        row = per_day.setdefault(day, {"day": day, "tokens": 0, "cost_usd": 0.0})
        for r in bucket.get("results", []):
            # Reported as a decimal string in cents.
            row["cost_usd"] += float(r.get("amount") or 0) / 100
    return {"days": sorted(per_day.values(), key=lambda d: d["day"]), "models": models}


def cached_fetch() -> dict:
    global _cached
    with _lock:
        if _cached and time.monotonic() - _cached[0] < CACHE_SECONDS:
            return _cached[1]
    data = fetch()
    with _lock:
        _cached = (time.monotonic(), data)
    return data


def clear() -> None:
    global _cached
    with _lock:
        _cached = None
