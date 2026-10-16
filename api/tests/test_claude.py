import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.modules.claude import admin_api, claude_code
from app.modules.claude.pricing import cost_usd


def _reply(when: datetime, msg_id: str, model="claude-opus-5-5", cwd="/home/nils/hub", **usage):
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": when.isoformat().replace("+00:00", "Z"),
            "sessionId": "s1",
            "requestId": f"req_{msg_id}",
            "cwd": cwd,
            "message": {
                "id": msg_id,
                "model": model,
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_read_input_tokens": 1000,
                    "cache_creation_input_tokens": 200,
                    "cache_creation": {"ephemeral_1h_input_tokens": 0},
                    **usage,
                },
            },
        }
    )


@pytest.fixture
def logs(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    monkeypatch.setenv("HUB_CLAUDE_LOGS_DIR", str(root))
    monkeypatch.setenv("HUB_TIMEZONE", "UTC")
    get_settings.cache_clear()
    claude_code._cache.clear()
    admin_api.clear()
    return root


def test_claude_code_usage_from_logs(admin_client, logs):
    now = datetime.now(UTC).replace(hour=12)
    project = logs / "-home-nils-hub"
    project.mkdir(parents=True)
    lines = [
        _reply(now, "m1"),
        _reply(now, "m1"),  # resumed session repeats the reply: counted once
        _reply(now - timedelta(days=2), "m2", model="claude-haiku-5-5", cwd="/home/nils/notes"),
        _reply(now, "m3", model="<synthetic>"),
        json.dumps({"type": "user", "message": {"content": "hi"}}),
        "not json",
        _reply(now - timedelta(days=40), "old"),
    ]
    (project / "s1.jsonl").write_text("\n".join(lines))

    code = admin_client.get("/api/claude/usage").json()["code"]
    assert code["found"] is True
    assert len(code["days"]) == 30
    per_reply = 100 + 50 + 1000 + 200
    assert code["today_tokens"] == per_reply
    assert code["tokens_30d"] == 2 * per_reply
    assert [m["name"] for m in code["models"]] == ["claude-opus-5-5", "claude-haiku-5-5"]
    assert {p["name"] for p in code["projects"]} == {"hub", "notes"}
    assert code["sessions_30d"] == 1
    opus = cost_usd("claude-opus-5-5", 100, 50, 1000, 200, 0)
    assert code["models"][0]["cost_usd"] == round(opus, 2)
    assert code["cache_hit_rate"] == round(2000 / (2000 + 600), 3)


def test_no_logs_is_not_an_error(admin_client, logs):
    usage = admin_client.get("/api/claude/usage").json()
    assert usage["code"]["found"] is False
    assert usage["code"]["tokens_30d"] == 0
    assert usage["api"] == {
        "configured": False,
        "error": None,
        "days": [],
        "models": [],
        "cost_30d": 0.0,
        "avg_cost_7d": 0.0,
    }
    assert usage["plan_usage_url"] == "https://claude.ai/settings/usage"


def test_prices_pick_the_most_specific_model():
    # Opus 5.5 is cheaper than Opus 5; a prefix match on "claude-opus-5" would overcharge.
    assert cost_usd("claude-opus-5-5", 1_000_000, 0, 0, 0, 0) == 4.0
    assert cost_usd("claude-opus-5", 1_000_000, 0, 0, 0, 0) == 5.0
    assert cost_usd("claude-sonnet-4-6", 0, 1_000_000, 0, 0, 0) == 15.0
    assert cost_usd("gpt-5", 1, 1, 0, 0, 0) is None


def test_api_spend_from_the_admin_api(admin_client, logs, monkeypatch):
    monkeypatch.setenv("HUB_ANTHROPIC_ADMIN_KEY", "sk-ant-admin01-test")
    get_settings.cache_clear()
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["x-api-key"] == "sk-ant-admin01-test"
        bucket = {"starting_at": "2026-10-15T00:00:00Z", "ending_at": "2026-10-16T00:00:00Z"}
        if request.url.path.endswith("usage_report/messages"):
            result = {
                "model": "claude-sonnet-5-5",
                "uncached_input_tokens": 1000,
                "cache_read_input_tokens": 0,
                "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
                "output_tokens": 500,
            }
        else:
            result = {"amount": "150.5", "currency": "USD"}
        return httpx.Response(
            200, json={"data": [{**bucket, "results": [result]}], "has_more": False}
        )

    real_client = httpx.Client
    monkeypatch.setattr(
        admin_api.httpx,
        "Client",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    api = admin_client.get("/api/claude/usage").json()["api"]
    assert api["configured"] is True and api["error"] is None
    assert api["days"] == [
        {
            "day": "2026-10-15",
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_write": 0,
            "tokens": 1500,
            "cost_usd": 1.5,  # cents in, dollars out
        }
    ]
    assert api["models"][0]["name"] == "claude-sonnet-5-5"
    assert seen[0].url.params["group_by[]"] == "model"
    # The key is never sent back to the browser.
    assert "sk-ant" not in admin_client.get("/api/claude/usage").text


def test_a_rejected_admin_key_is_explained(admin_client, logs, monkeypatch):
    monkeypatch.setenv("HUB_ANTHROPIC_ADMIN_KEY", "sk-ant-api03-not-admin")
    get_settings.cache_clear()
    real_client = httpx.Client
    monkeypatch.setattr(
        admin_api.httpx,
        "Client",
        lambda **kw: real_client(
            transport=httpx.MockTransport(lambda r: httpx.Response(403, json={})), **kw
        ),
    )
    api = admin_client.get("/api/claude/usage").json()["api"]
    assert "isn't an Admin API key" in api["error"]


def test_claude_page_is_owner_only(admin_client, logs):
    with TestClient(app, client=("192.168.1.40", 50000)) as other:
        other.post("/api/auth/device")
        assert other.get("/api/claude/usage").status_code == 403
        assert "claude" not in [m["id"] for m in other.get("/api/modules").json()]
