"""Earn apps page: the API reads the Pi's status file; the Pi-side script parses and counts."""

import importlib.util
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from app.config import get_settings

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pi-earn-status.py"
spec = importlib.util.spec_from_file_location("pi_earn_status", SCRIPT)
pi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pi)

NOT_INSTALLED = {"installed": False, "running": False, "state": "not installed", "counter": None}


def write_status(apps: dict, at: datetime | None = None) -> None:
    at = at or datetime.now(UTC)
    get_settings().earn_status_path.write_text(
        json.dumps({"generated_at": at.isoformat(), "apps": apps})
    )


def test_not_set_up_yet(admin_client):
    status = admin_client.get("/api/earn").json()
    assert status == {"generated_at": None, "stale": True, "apps": {}, "error": ""}


def test_reads_the_pis_report(admin_client):
    earnapp = {
        "installed": True,
        "running": True,
        "state": "running",
        "counter": 5000,
        "today_bytes": 1000,
        "total_bytes": 5000,
        "counted_since": "2026-11-17",
        "log": ["started"],
    }
    write_status({"earnapp": earnapp, "pawns": NOT_INSTALLED})
    status = admin_client.get("/api/earn").json()
    assert status["stale"] is False
    assert status["apps"]["earnapp"]["total_bytes"] == 5000
    assert status["apps"]["earnapp"]["log"] == ["started"]
    assert status["apps"]["pawns"]["installed"] is False


def test_old_report_is_stale_and_broken_one_is_reported(admin_client):
    write_status({}, at=datetime.now(UTC) - timedelta(hours=1))
    assert admin_client.get("/api/earn").json()["stale"] is True
    get_settings().earn_status_path.write_text("{not json")
    status = admin_client.get("/api/earn").json()
    assert status["generated_at"] is None
    assert "couldn't be read" in status["error"]


def test_only_for_the_owner(admin_client):
    tiles = {m["id"]: m for m in admin_client.get("/api/modules").json()}
    assert tiles["earn"]["owner_only"] is True
    admin_client.cookies.clear()
    admin_client.post("/api/auth/device")
    assert "earn" not in {m["id"] for m in admin_client.get("/api/modules").json()}
    assert admin_client.get("/api/earn").status_code == 403


def test_systemd_props_and_net_dev():
    props = pi.systemd_props("LoadState=loaded\nActiveState=active\nIPIngressBytes=[not set]\n")
    assert props == {"LoadState": "loaded", "ActiveState": "active", "IPIngressBytes": "[not set]"}
    net_dev = """Inter-|   Receive                            |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets
    lo: 500 5 0 0 0 0 0 0 500 5 0 0 0 0 0 0
  eth0: 1000 10 0 0 0 0 0 0 2000 20 0 0 0 0 0 0
"""
    assert pi.net_dev_bytes(net_dev) == 3000


def test_traffic_carries_over_restarts_and_days():
    day1, day2 = date(2026, 11, 17), date(2026, 11, 18)
    first = pi.add_traffic({"counter": 100}, {}, day1)
    assert (first["today_bytes"], first["total_bytes"], first["counted_since"]) == (
        100,
        100,
        "2026-11-17",
    )
    later = pi.add_traffic({"counter": 250}, first, day1)
    assert (later["today_bytes"], later["total_bytes"]) == (250, 250)
    # The app restarted overnight: its counter began again from zero.
    restarted = pi.add_traffic({"counter": 40}, later, day2)
    assert (restarted["today_bytes"], restarted["total_bytes"]) == (40, 290)
    # Stopped: nothing new is counted, totals stay.
    stopped = pi.add_traffic({"counter": None}, restarted, day2)
    assert (stopped["today_bytes"], stopped["total_bytes"]) == (40, 290)


def test_log_tail_keeps_the_last_lines_short():
    lines = pi.log_tail("\n".join(f"line {i}" for i in range(50)) + "\n\n" + "x" * 1000)
    assert len(lines) == pi.LOG_LINES
    assert lines[-2] == "line 49"
    assert len(lines[-1]) == pi.LOG_LINE_MAX
