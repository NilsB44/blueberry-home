import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlmodel import Session

from app import db as db_module
from app.config import get_settings
from app.modules.network import health, monitor
from app.modules.network.models import Outage

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pi-network-scan.py"
spec = importlib.util.spec_from_file_location("pi_network_scan", SCRIPT)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)

PI = {"mac": "d8:3a:dd:00:00:01", "ip": "192.168.1.2", "hostname": "hub", "is_pi": True}
ROUTER = {"mac": "00:11:22:33:44:55", "ip": "192.168.1.1", "hostname": "router"}
LAPTOP = {"mac": "3c:22:fb:aa:bb:cc", "ip": "192.168.1.30", "hostname": "Nils-MacBook"}
# A phone's private address: the second hex digit is 2, 6, a or e.
STRANGER = {"mac": "4a:10:20:30:40:50", "ip": "192.168.1.77", "hostname": ""}


def write_scan(devices: list[dict], at: datetime | None = None) -> None:
    path = get_settings().network_scan_path
    path.write_text(
        json.dumps(
            {
                "generated_at": (at or datetime.now(UTC)).isoformat(),
                "interface": "wlan0",
                "network": "192.168.1.0/24",
                "gateway": "192.168.1.1",
                "devices": devices,
            }
        )
    )
    # A new mtime even when two scans land within the same clock tick.
    monitor.state.scan_mtime = None


@pytest.fixture
def guest_client(admin_client):
    """A second device in the house, which isn't an admin."""
    admin_cookie = admin_client.cookies.get("hub_session")
    admin_client.cookies.clear()
    assert admin_client.post("/api/auth/device").json()["is_admin"] is False
    yield admin_client
    admin_client.cookies.clear()
    admin_client.cookies.set("hub_session", admin_cookie)


def test_network_tile_is_ready(admin_client):
    tiles = {m["id"]: m for m in admin_client.get("/api/modules").json()}
    assert tiles["network"]["status"] == "ready"


def test_first_scan_is_the_baseline_and_later_newcomers_are_flagged(admin_client):
    write_scan([PI, ROUTER, LAPTOP])
    devices = admin_client.get("/api/network/devices").json()
    assert [d["ip"] for d in devices] == ["192.168.1.1", "192.168.1.2", "192.168.1.30"]
    assert all(d["known"] and d["online"] for d in devices)
    assert devices[0]["is_gateway"] and devices[1]["is_pi"]

    write_scan([PI, ROUTER, STRANGER], at=datetime.now(UTC) + timedelta(minutes=5))
    devices = admin_client.get("/api/network/devices").json()
    # New first, then online, then offline.
    assert [(d["mac"], d["known"], d["online"]) for d in devices] == [
        (STRANGER["mac"], False, True),
        (ROUTER["mac"], True, True),
        (PI["mac"], True, True),
        (LAPTOP["mac"], True, False),
    ]
    assert devices[0]["private_mac"] is True and devices[1]["private_mac"] is False
    scan = admin_client.get("/api/network/overview").json()["scan"]
    assert scan["online"] == 3
    assert scan["new_devices"] == 1
    assert scan["stale"] is False


def test_admin_names_and_acknowledges_devices(admin_client):
    write_scan([ROUTER])
    admin_client.get("/api/network/devices")
    write_scan([ROUTER, STRANGER, LAPTOP])
    admin_client.get("/api/network/devices")
    resp = admin_client.patch(
        f"/api/network/devices/{STRANGER['mac'].upper()}",
        json={"name": " Anna's phone ", "known": True},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Anna's phone"
    assert resp.json()["known"] is True
    assert admin_client.get("/api/network/overview").json()["scan"]["new_devices"] == 1

    assert admin_client.post("/api/network/devices/acknowledge").status_code == 204
    assert admin_client.get("/api/network/overview").json()["scan"]["new_devices"] == 0

    assert admin_client.delete(f"/api/network/devices/{LAPTOP['mac']}").status_code == 204
    assert len(admin_client.get("/api/network/devices").json()) == 2
    assert admin_client.delete(f"/api/network/devices/{LAPTOP['mac']}").status_code == 404


def test_an_old_scan_shows_everyone_offline(admin_client):
    write_scan([ROUTER], at=datetime.now(UTC) - timedelta(hours=1))
    scan = admin_client.get("/api/network/overview").json()["scan"]
    assert scan["stale"] is True
    assert scan["online"] == 0


def test_a_broken_scan_file_is_ignored(admin_client):
    get_settings().network_scan_path.write_text('{"devices": [{"mac": "nope"}]}')
    assert admin_client.get("/api/network/devices").json() == []
    assert admin_client.get("/api/network/overview").json()["scan"]["at"] is None


def test_everyone_sees_the_overview_but_only_admins_the_devices(guest_client):
    write_scan([ROUTER, LAPTOP])
    resp = guest_client.get("/api/network/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scan"]["online"] == 2
    assert body["scan"]["new_devices"] is None
    assert body["refused_7d"] is None
    assert "health" in body and "internet" in body
    assert guest_client.get("/api/network/devices").status_code == 403
    assert guest_client.patch(f"/api/network/devices/{LAPTOP['mac']}", json={}).status_code == 403
    assert guest_client.delete(f"/api/network/devices/{LAPTOP['mac']}").status_code == 403
    assert guest_client.post("/api/network/speedtest").status_code == 403


def test_overview_counts_refused_visits_from_the_security_log(admin_client):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, client=("100.101.102.103", 50000)) as vpn:
        vpn.get("/api/auth/me")
        vpn.get("/api/auth/me")
    admin_client.get("/api/security/attempts")  # writes the counted attempts
    assert admin_client.get("/api/network/overview").json()["refused_7d"] == 2


def test_outages_need_two_failed_checks_in_a_row(admin_client):
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    results = [12.0, None, 15.0, None, None, None, 20.0, 18.0]
    with Session(db_module.get_engine()) as session:
        for i, latency in enumerate(results):
            monitor.record_probe(session, latency, start + timedelta(minutes=i))
            if i == 4:
                assert monitor.state.up is False
        outages = session.exec(monitor.select(Outage)).all()
    assert len(outages) == 1
    assert outages[0].ended_at is not None

    internet = admin_client.get("/api/network/overview").json()["internet"]
    assert internet["up"] is True
    assert internet["latency_ms"] == 18.0
    assert internet["uptime_24h"] == pytest.approx(4 / 8)
    assert internet["outages_7d"] == 1
    history = admin_client.get("/api/network/history").json()
    assert history["outages"][0]["minutes"] == 3.0
    assert history["hours"][0]["latency_ms"] == pytest.approx((12 + 15 + 20 + 18) / 4, abs=0.1)


def test_hours_already_written_and_still_in_memory_add_up(admin_client):
    now = datetime.now(UTC)
    with Session(db_module.get_engine()) as session:
        monitor.record_probe(session, 10.0, now)
        monitor.flush(session, now)
        monitor.record_probe(session, None, now)
        rows = monitor.hours_since(session, now - timedelta(hours=1))
    assert [(r.checks, r.failures) for r in rows] == [(2, 1)]


def test_speed_test_measures_against_the_speed_server():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/__down":
            return httpx.Response(200, content=b"x" * int(request.url.params["bytes"]))
        assert request.url.path == "/__up"
        assert len(request.content) == monitor.UPLOAD_BYTES
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        ping, down, up = monitor.measure_speed(client, "https://speed.test")
    assert ping >= 0 and down > 0 and up > 0


def test_speed_test_endpoint_saves_results(admin_client, monkeypatch):
    monkeypatch.setattr(monitor, "measure_speed", lambda client, base: (9.5, 480.2, 95.1))
    resp = admin_client.post("/api/network/speedtest")
    assert resp.status_code == 201
    assert resp.json()["down_mbps"] == 480.2
    assert admin_client.get("/api/network/overview").json()["speed"]["up_mbps"] == 95.1
    assert len(admin_client.get("/api/network/history").json()["speedtests"]) == 1


def test_a_failed_speed_test_says_so(admin_client, monkeypatch):
    def offline(client, base):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(monitor, "measure_speed", offline)
    body = admin_client.post("/api/network/speedtest").json()
    assert body["down_mbps"] is None
    assert "Couldn't reach" in body["error"]


def test_speed_test_is_due_every_few_hours(admin_client, monkeypatch):
    now = datetime.now(UTC)
    monitor.state.up = True
    monkeypatch.setattr(monitor, "measure_speed", lambda client, base: (1.0, 2.0, 3.0))
    with Session(db_module.get_engine()) as session:
        assert monitor.speedtest_due(session, now)
        monitor.run_speedtest(session, "scheduled")
        assert not monitor.speedtest_due(session, now)
        assert monitor.speedtest_due(session, now + timedelta(hours=6, minutes=1))
        monitor.state.up = False
        assert not monitor.speedtest_due(session, now + timedelta(hours=7))


@pytest.fixture
def fake_pi(tmp_path, monkeypatch):
    proc, sys = tmp_path / "proc", tmp_path / "sys"
    proc.mkdir()
    (proc / "uptime").write_text("93784.12 300000.00\n")
    (proc / "loadavg").write_text("0.52 0.40 0.31 1/400 1234\n")
    (proc / "meminfo").write_text(
        "MemTotal:        8000000 kB\nMemFree:          100000 kB\nMemAvailable:    4000000 kB\n"
    )
    zone = sys / "class" / "thermal" / "thermal_zone0"
    zone.mkdir(parents=True)
    (zone / "type").write_text("cpu-thermal\n")
    (zone / "temp").write_text("52100\n")
    firmware = sys / "devices" / "platform" / "soc" / "soc:firmware"
    firmware.mkdir(parents=True)
    (firmware / "get_throttled").write_text("0x0\n")
    monkeypatch.setattr(health, "PROC", proc)
    monkeypatch.setattr(health, "SYS", sys)
    return zone, firmware


def test_pi_health_reads_proc_and_sys(fake_pi):
    h = health.read()
    assert h.status == "ok"
    assert h.uptime_seconds == pytest.approx(93784.12)
    assert h.temperature_c == 52.1
    assert h.load == [0.52, 0.40, 0.31]
    assert h.memory_total_bytes == 8000000 * 1024
    assert h.memory_available_bytes == 4000000 * 1024
    assert h.throttled_now == []


def test_pi_health_flags_heat_and_power(fake_pi):
    zone, firmware = fake_pi
    (zone / "temp").write_text("84000\n")
    # Under-voltage now (bit 0) and since boot (bit 16).
    (firmware / "get_throttled").write_text("0x10001\n")
    h = health.read()
    assert h.status == "fail"
    assert h.throttled_now == ["under-voltage"]
    assert h.throttled_since_boot == ["under-voltage"]
    assert any("hot" in n for n in h.notes)


def test_pi_health_copes_without_proc_or_sys(tmp_path, monkeypatch):
    monkeypatch.setattr(health, "PROC", tmp_path / "none")
    monkeypatch.setattr(health, "SYS", tmp_path / "none")
    h = health.read()
    assert h.temperature_c is None and h.uptime_seconds is None and h.load is None


def test_scanner_reads_the_neighbour_table(monkeypatch):
    neigh = [
        {"dst": "192.168.1.1", "lladdr": "00:11:22:33:44:55", "state": ["REACHABLE"]},
        {"dst": "192.168.1.30", "lladdr": "3C:22:FB:AA:BB:CC", "state": ["STALE"]},
        {"dst": "192.168.1.40", "state": ["FAILED"]},
        {"dst": "192.168.1.50", "lladdr": "aa:aa:aa:aa:aa:aa", "state": ["INCOMPLETE"]},
        {"dst": "10.0.0.5", "lladdr": "bb:bb:bb:bb:bb:bb", "state": ["REACHABLE"]},
    ]
    monkeypatch.setattr(scanner, "run", lambda *cmd, timeout=30: json.dumps(neigh))
    import ipaddress

    found = scanner.neighbours("wlan0", ipaddress.ip_network("192.168.1.0/24"))
    assert found == {"00:11:22:33:44:55": "192.168.1.1", "3c:22:fb:aa:bb:cc": "192.168.1.30"}


def test_scanner_output_is_what_the_hub_reads(monkeypatch, tmp_path):
    def fake_run(*cmd, timeout=30):
        if cmd[:4] == ("ip", "-j", "-4", "route"):
            return json.dumps([{"dst": "default", "gateway": "192.168.1.1", "dev": "wlan0"}])
        if cmd[:4] == ("ip", "-j", "-4", "addr"):
            return json.dumps(
                [
                    {
                        "address": "D8:3A:DD:00:00:01",
                        "addr_info": [{"family": "inet", "local": "192.168.1.2", "prefixlen": 24}],
                    }
                ]
            )
        if cmd[:4] == ("ip", "-j", "-4", "neigh"):
            return json.dumps(
                [{"dst": "192.168.1.1", "lladdr": "00:11:22:33:44:55", "state": ["REACHABLE"]}]
            )
        return None

    monkeypatch.setattr(scanner, "run", fake_run)
    monkeypatch.setattr(scanner, "sweep", lambda network, own: None)
    monkeypatch.setattr(scanner, "hostname", lambda ip: "router" if ip.endswith(".1") else "")
    report = scanner.scan()
    scan = monitor.Scan.model_validate(report)
    assert [(d.ip, d.hostname, d.is_pi) for d in scan.devices] == [
        ("192.168.1.1", "router", False),
        ("192.168.1.2", "", True),
    ]
    out = tmp_path / "scan.json"
    scanner.write(report, out)
    assert json.loads(out.read_text())["gateway"] == "192.168.1.1"
