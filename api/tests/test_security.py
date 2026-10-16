import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.auth import lockout
from app.config import get_settings
from app.main import app
from app.modules.security import checks, scheduler, tracker

VPN_IP = "100.101.102.103"
query_osv = checks.query_osv


@pytest.fixture(autouse=True)
def offline_osv(monkeypatch):
    monkeypatch.setattr(checks, "query_osv", lambda packages: {})


def _away(client: TestClient) -> TestClient:
    """The same device, now out of the house and on the VPN."""
    away = TestClient(app, client=(VPN_IP, 50000))
    if token := client.cookies.get("hub_session"):
        away.cookies.set("hub_session", token)
    return away


def _check(report: dict, check_id: str) -> dict:
    return next(c for c in report["checks"] if c["id"] == check_id)


def test_vpn_is_refused_while_away_access_is_off(admin_client):
    with _away(admin_client) as away:
        resp = away.get("/api/auth/me")
    assert resp.status_code == 403
    assert "Away access is off" in resp.json()["detail"]
    attempts = admin_client.get("/api/security/attempts").json()
    assert [(a["kind"], a["ip"], a["count"]) for a in attempts] == [("blocked", VPN_IP, 1)]
    assert attempts[0]["from_internet"] is False


def test_away_access_lets_in_devices_that_joined_at_home(admin_client):
    resp = admin_client.put("/api/security/away", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    assert resp.json()["changed_by"] == "Nils"
    with _away(admin_client) as away:
        assert away.get("/api/auth/me").json()["username"] == "nils"


def test_new_devices_cant_join_from_away(admin_client):
    admin_client.put("/api/security/away", json={"enabled": True})
    with TestClient(app, client=(VPN_IP, 50000)) as stranger:
        assert stranger.post("/api/auth/device").status_code == 403
        assert stranger.get("/api/auth/me").status_code == 401
        resp = stranger.post(
            "/api/auth/login", json={"username": "nils", "password": "correct horse battery"}
        )
        assert resp.status_code == 403


def test_away_access_can_be_turned_off_but_not_on_from_away(admin_client):
    admin_client.put("/api/security/away", json={"enabled": True})
    with _away(admin_client) as away:
        assert away.get("/api/security/away").json()["can_enable"] is False
        assert away.put("/api/security/away", json={"enabled": False}).status_code == 200
        # Now off, so even the away device itself is shut out.
        assert away.put("/api/security/away", json={"enabled": True}).status_code == 403
    assert admin_client.get("/api/security/away").json()["enabled"] is False


def test_security_is_for_the_owner_only(admin_client):
    assert admin_client.get("/api/auth/me").json()["is_owner"] is True
    other_admin = {"username": "bob", "display_name": "Bob", "password": "another long one"}
    assert (
        admin_client.post("/api/users", json={**other_admin, "is_admin": True}).status_code == 201
    )
    with TestClient(app, client=("192.168.1.40", 50000)) as other:
        other.post("/api/auth/device")
        assert other.get("/api/security/away").status_code == 403
        with TestClient(app, client=("192.168.1.41", 50000)) as bob:
            bob.post("/api/auth/login", json={"username": "bob", "password": "another long one"})
            assert bob.get("/api/auth/me").json()["is_admin"] is True
            for client in (other, bob):
                assert client.put("/api/security/away", json={"enabled": True}).status_code == 403
                assert client.post("/api/security/reports").status_code == 403
                assert client.get("/api/security/sessions").status_code == 403
                assert "security" not in [m["id"] for m in client.get("/api/modules").json()]
    assert "security" in [m["id"] for m in admin_client.get("/api/modules").json()]


def test_the_first_device_owns_the_hub(client):
    first = client.post("/api/auth/device").json()
    assert first["is_owner"] is True
    with TestClient(app, client=("192.168.1.40", 50000)) as second:
        assert second.post("/api/auth/device").json()["is_owner"] is False


def test_away_access_turns_itself_off(admin_client):
    resp = admin_client.put("/api/security/away", json={"enabled": True, "hours": 4})
    assert resp.json()["enabled"] is True
    expires = datetime.fromisoformat(resp.json()["expires_at"]).replace(tzinfo=UTC)
    assert timedelta(hours=3, minutes=59) < expires - datetime.now(UTC) <= timedelta(hours=4)
    assert (
        admin_client.put("/api/security/away", json={"enabled": True, "hours": 5}).status_code
        == 422
    )

    from sqlmodel import Session

    from app.db import get_engine
    from app.modules.security.remote import away_setting, expire_away

    later = datetime.now(UTC) + timedelta(hours=5)
    with Session(get_engine()) as session:
        setting = away_setting(session)
        setting.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.add(setting)
        session.commit()
    with _away(admin_client) as away:
        assert away.get("/api/auth/me").status_code == 403
    assert admin_client.get("/api/security/away").json()["enabled"] is False
    with Session(get_engine()) as session:
        assert expire_away(session, later) is True
    actions = [e["action"] for e in admin_client.get("/api/security/events").json()]
    assert actions == ["away-expired", "away-on"]


def test_owner_sees_devices_and_can_sign_one_out(admin_client):
    with TestClient(app, client=("192.168.1.40", 50000)) as other:
        other.post("/api/auth/device")
        assert other.get("/api/auth/me").status_code == 200
        devices = admin_client.get("/api/security/sessions").json()
        assert [d["this_device"] for d in devices] == [False, True]
        mine, theirs = devices[1], devices[0]
        assert mine["is_owner"] and mine["last_ip"] == "192.168.1.23"
        assert admin_client.delete(f"/api/security/sessions/{mine['id']}").status_code == 400
        assert admin_client.delete(f"/api/security/sessions/{theirs['id']}").status_code == 204
        assert other.get("/api/auth/me").status_code == 401
    events = admin_client.get("/api/security/events").json()
    assert events[0]["action"] == "signed-out"
    assert events[0]["who"] == "Nils"


def test_wrong_passwords_lock_logins_for_a_while(admin_client):
    admin_client.cookies.clear()
    wrong = {"username": "nils", "password": "nope"}
    for _ in range(lockout.MAX_FAILURES):
        assert admin_client.post("/api/auth/login", json=wrong).status_code == 401
    resp = admin_client.post("/api/auth/login", json={**wrong, "password": "correct horse battery"})
    assert resp.status_code == 429
    assert "Try again" in resp.json()["detail"]
    lockout.clear()
    resp = admin_client.post("/api/auth/login", json={**wrong, "password": "correct horse battery"})
    assert resp.status_code == 200
    assert admin_client.get("/api/security/events").json()[0]["action"] == "lockout"


def test_a_quiet_week_reports_ok_apart_from_the_missing_pi_report(admin_client):
    report = admin_client.post("/api/security/reports").json()
    statuses = {c["id"]: c["status"] for c in report["checks"]}
    assert statuses == {
        "network-ranges": "ok",
        "away-access": "ok",
        "refused": "ok",
        "failed-logins": "ok",
        "people": "ok",
        "cookies": "warn",  # the test client runs over plain HTTP
        "dependencies": "ok",
        "pi-report": "warn",
    }
    assert report["status"] == "warn"
    assert report["trigger"] == "manual"
    latest = admin_client.get("/api/security/schedule").json()["latest"]
    assert latest["id"] == report["id"]
    assert admin_client.get("/api/security/reports").json()[0]["counts"] == {"ok": 6, "warn": 2}


def test_internet_visitors_fail_the_check(admin_client):
    tracker.record("blocked", "203.0.113.9", "/api/health")
    tracker.record("blocked", "8.8.8.8", "/")
    report = admin_client.post("/api/security/reports").json()
    refused = _check(report, "refused")
    assert refused["status"] == "fail"
    assert "port forwarding" in refused["summary"]
    assert report["status"] == "fail"


def test_vpn_visitors_while_off_only_warn(admin_client):
    tracker.record("blocked", VPN_IP, "/")
    assert _check(admin_client.post("/api/security/reports").json(), "refused")["status"] == "warn"


def test_failed_logins_are_counted(admin_client, monkeypatch):
    monkeypatch.setattr(lockout, "MAX_FAILURES", 100)
    for _ in range(checks.FAILED_LOGINS_WARN):
        admin_client.post("/api/auth/login", json={"username": "nils", "password": "nope"})
    logins = _check(admin_client.post("/api/security/reports").json(), "failed-logins")
    assert logins["status"] == "warn"
    assert "@nils" in logins["details"][0]


def test_vulnerable_packages_fail_and_offline_is_unknown(admin_client, monkeypatch):
    monkeypatch.setattr(checks, "query_osv", lambda p: {"starlette 0.1": ["GHSA-xxxx"]})
    deps = _check(admin_client.post("/api/security/reports").json(), "dependencies")
    assert deps["status"] == "fail"
    assert deps["details"] == ["starlette 0.1: GHSA-xxxx"]

    def offline(_):
        raise httpx.ConnectError("no internet")

    monkeypatch.setattr(checks, "query_osv", offline)
    deps = _check(admin_client.post("/api/security/reports").json(), "dependencies")
    assert deps["status"] == "unknown"


def test_osv_results_are_matched_to_packages(monkeypatch):
    def fake_post(url, json, timeout):
        assert [q["package"]["name"] for q in json["queries"]] == ["fastapi", "uvicorn"]
        return httpx.Response(
            200,
            json={"results": [{}, {"vulns": [{"id": "PYSEC-1"}]}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(checks.httpx, "post", fake_post)
    found = query_osv({"fastapi": "1.0", "uvicorn": "0.1"})
    assert found == {"uvicorn 0.1": ["PYSEC-1"]}


def test_the_pi_report_is_merged_in(admin_client):
    path = get_settings().host_report_path
    path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "hostname": "hub",
                "checks": [
                    {"id": "ssh", "title": "SSH", "status": "fail", "summary": "Passwords on"},
                    {"id": "firewall", "title": "Firewall", "status": "ok", "summary": "On"},
                ],
            }
        )
    )
    report = admin_client.post("/api/security/reports").json()
    pi = [c for c in report["checks"] if c["group"] == "pi"]
    assert [(c["id"], c["status"]) for c in pi] == [("ssh", "fail"), ("firewall", "ok")]
    assert report["status"] == "fail"


def test_a_stale_or_broken_pi_report_warns(admin_client):
    path = get_settings().host_report_path
    old = datetime.now(UTC) - timedelta(days=10)
    path.write_text(json.dumps({"generated_at": old.isoformat(), "checks": []}))
    stale = _check(admin_client.post("/api/security/reports").json(), "pi-report")
    assert stale["status"] == "warn"
    assert "10 days ago" in stale["summary"]
    path.write_text("not json")
    broken = _check(admin_client.post("/api/security/reports").json(), "pi-report")
    assert broken["summary"] == "The Pi's report couldn't be read."


def test_public_trusted_networks_fail(admin_client, monkeypatch):
    monkeypatch.setenv("HUB_TRUSTED_NETWORKS", '["192.168.0.0/16", "0.0.0.0/0"]')
    get_settings.cache_clear()
    ranges = checks.check_network_ranges()
    assert ranges.status == "fail"
    assert "0.0.0.0/0" in ranges.details[0]


def test_tracker_caps_distinct_addresses(monkeypatch):
    monkeypatch.setattr(tracker, "MAX_KEYS", 3)
    for i in range(10):
        tracker.record("blocked", f"203.0.113.{i}", "/")
    keys = {ip for (_, ip, _) in tracker._pending}
    assert len(keys) == 4
    assert tracker.OVERFLOW_IP in keys


def test_schedule_slots(monkeypatch):
    monkeypatch.setenv("HUB_TIMEZONE", "UTC")
    get_settings.cache_clear()
    # Sunday 4:00 by default. A Wednesday's last slot is the Sunday before.
    wednesday = datetime(2026, 10, 14, 12, tzinfo=UTC)
    assert scheduler.last_slot(wednesday) == datetime(2026, 10, 11, 4, tzinfo=UTC)
    assert scheduler.next_slot(wednesday) == datetime(2026, 10, 18, 4, tzinfo=UTC)
    # Sunday before 4:00 still belongs to the previous week.
    early_sunday = datetime(2026, 10, 18, 3, tzinfo=UTC)
    assert scheduler.last_slot(early_sunday) == datetime(2026, 10, 11, 4, tzinfo=UTC)
    assert scheduler.last_slot(datetime(2026, 10, 18, 4, tzinfo=UTC)) == datetime(
        2026, 10, 18, 4, tzinfo=UTC
    )


def test_scheduled_check_runs_once_per_week(admin_client, monkeypatch):
    monkeypatch.setenv("HUB_TIMEZONE", "UTC")
    get_settings.cache_clear()
    scheduler.tick()
    scheduler.tick()
    reports = admin_client.get("/api/security/reports").json()
    assert [r["trigger"] for r in reports] == ["scheduled"]


def test_older_hubs_get_their_first_admin_as_owner(client):
    from sqlmodel import Session

    from app.auth.models import User
    from app.db import _ensure_owner, get_engine

    with Session(get_engine()) as session:
        session.add(User(username="guest", display_name="Guest"))
        session.add(User(username="nils", display_name="Nils", is_admin=True))
        session.commit()
    _ensure_owner(get_engine())
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.is_owner == True)).one()  # noqa: E712
    assert owner.username == "nils"


def test_ownership_moves_only_from_the_pi(admin_client, capsys):
    from app import owner

    other_admin = {"username": "bob", "display_name": "Bob", "password": "another long one"}
    admin_client.post("/api/users", json={**other_admin, "is_admin": False})
    assert owner.main(["nobody"]) == 1
    assert owner.main(["bob"]) == 0
    assert "@bob (Bob) now owns the hub." in capsys.readouterr().out
    assert admin_client.get("/api/auth/me").json()["is_owner"] is False
    assert admin_client.get("/api/security/away").status_code == 403
