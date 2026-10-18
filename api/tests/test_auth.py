from fastapi.testclient import TestClient

from app.auth.device import device_from_user_agent, new_username
from app.config import get_settings
from app.main import app
from tests.conftest import ADMIN, IPHONE_UA


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_first_run_setup_creates_admin_and_logs_in(client):
    assert client.get("/api/auth/setup").json() == {"needs_setup": True}
    resp = client.post("/api/auth/setup", json=ADMIN)
    assert resp.status_code == 201
    assert resp.json()["is_admin"] is True
    assert client.get("/api/auth/me").json()["username"] == "nils"
    assert client.get("/api/auth/setup").json() == {"needs_setup": False}


def test_setup_only_works_once(admin_client):
    other = {**ADMIN, "username": "mallory"}
    assert admin_client.post("/api/auth/setup", json=other).status_code == 409


def test_setup_rejects_short_password(client):
    resp = client.post("/api/auth/setup", json={**ADMIN, "password": "short"})
    assert resp.status_code == 422


def test_logout_then_login(admin_client):
    assert admin_client.post("/api/auth/logout").status_code == 204
    assert admin_client.get("/api/auth/me").status_code == 401

    bad = admin_client.post("/api/auth/login", json={"username": "nils", "password": "nope"})
    assert bad.status_code == 401
    unknown = admin_client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    assert unknown.status_code == 401

    ok = admin_client.post(
        "/api/auth/login", json={"username": "Nils", "password": ADMIN["password"]}
    )
    assert ok.status_code == 200
    assert admin_client.get("/api/auth/me").status_code == 200


def test_session_cookie_is_httponly(client):
    resp = client.post("/api/auth/setup", json=ADMIN)
    cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_admin_can_add_guest_who_cannot_add_users(admin_client):
    guest = {"username": "sam", "display_name": "Sam", "password": "guest password 1"}
    assert admin_client.post("/api/users", json=guest).status_code == 201
    assert admin_client.post("/api/users", json=guest).status_code == 409
    assert len(admin_client.get("/api/users").json()) == 2

    admin_client.post("/api/auth/logout")
    admin_client.post("/api/auth/login", json={"username": "sam", "password": guest["password"]})
    assert admin_client.post("/api/users", json={**guest, "username": "bob"}).status_code == 403


def test_modules_requires_login(client):
    assert client.get("/api/modules").status_code == 401


def test_modules_lists_tiles(admin_client):
    ids = [m["id"] for m in admin_client.get("/api/modules").json()]
    assert ids[:3] == ["french", "mandarin", "assistant"]
    assert "poker" in ids
    assert {"french", "poker", "tetris", "mandarin"} <= set(ids)


def test_first_device_joins_without_password_and_is_admin(client):
    resp = client.post("/api/auth/device", headers={"user-agent": IPHONE_UA})
    assert resp.status_code == 201
    me = resp.json()
    assert me["display_name"] == "iPhone"
    assert me["device"] == "iPhone"
    assert me["username"].startswith("iphone-")
    assert me["is_admin"] is True
    assert me["has_password"] is False
    assert "max-age=315360000" in resp.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").json()["id"] == me["id"]


def test_second_device_is_a_separate_person(client):
    first = client.post("/api/auth/device").json()
    client.cookies.clear()
    second = client.post("/api/auth/device").json()
    assert second["id"] != first["id"]
    assert second["is_admin"] is False
    assert len(client.get("/api/users").json()) == 2


def test_rename_myself(client):
    client.post("/api/auth/device")
    resp = client.patch("/api/auth/me", json={"username": "nils", "display_name": "Nils"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "nils"
    assert client.get("/api/auth/me").json()["display_name"] == "Nils"
    assert client.patch("/api/auth/me", json={"username": "Bad Name"}).status_code == 422


def test_rename_to_taken_username_conflicts(admin_client):
    admin_client.cookies.clear()
    admin_client.post("/api/auth/device")
    assert admin_client.patch("/api/auth/me", json={"username": "nils"}).status_code == 409


def test_device_person_cannot_log_in_with_a_password(client):
    username = client.post("/api/auth/device").json()["username"]
    for password in ["", "not-a-real-password"]:
        resp = client.post(
            "/api/auth/login", json={"username": username, "password": password or "x"}
        )
        assert resp.status_code == 401


def test_device_can_take_over_an_older_password_account(admin_client):
    admin_client.cookies.clear()
    admin_client.post("/api/auth/device")
    resp = admin_client.post(
        "/api/auth/login", json={"username": "nils", "password": ADMIN["password"]}
    )
    assert resp.status_code == 200
    assert admin_client.get("/api/auth/me").json()["username"] == "nils"


def test_outside_addresses_are_refused():
    for ip in ["8.8.8.8", "2001:4860:4860::8888", "testclient"]:
        with TestClient(app, client=(ip, 50000)) as outsider:
            assert outsider.get("/api/health").status_code == 403
            assert outsider.post("/api/auth/device").status_code == 403


def test_home_network_addresses_are_let_in():
    for ip in [
        "127.0.0.1",
        "10.0.0.5",
        "172.20.1.2",
        "192.168.50.9",
        "fd12::1",
        "::ffff:192.168.1.4",
    ]:
        with TestClient(app, client=(ip, 50000)) as device:
            assert device.get("/api/health").status_code == 200


def test_device_names_from_user_agents():
    android = "Mozilla/5.0 (Linux; Android 14; Pixel 7 Build/UQ1A) AppleWebKit/537.36 Mobile Safari"
    reduced = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/130 Mobile Safari"
    mac = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1"
    win = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130"
    assert device_from_user_agent(android) == "Pixel 7"
    assert device_from_user_agent(reduced) == "Android phone"
    assert device_from_user_agent(mac) == "Mac"
    assert device_from_user_agent(win) == "Windows PC"
    assert device_from_user_agent(None) == "Device"
    assert new_username("Nils's iPhone").startswith("nils-s-iphone-")


def test_websites_pointing_their_own_name_at_the_hub_are_refused(client):
    # DNS rebinding: evil.example resolves to the Pi, so the request comes from a home phone.
    for host in ["evil.example", "evil.example:80", "hub.home.evil.example"]:
        assert client.get("/api/health", headers={"host": host}).status_code == 403
    for host in ["hub.home", "hub.home:8443", "raspberrypi.local", "192.168.1.5", "[fd12::1]:80"]:
        assert client.get("/api/health", headers={"host": host}).status_code == 200
    assert client.get("/api/health", headers={"host": "pi.tail1234.ts.net"}).status_code == 200


def test_extra_allowed_hosts(client, monkeypatch):
    monkeypatch.setenv("HUB_ALLOWED_HOSTS", '["hub.example.com"]')
    get_settings.cache_clear()
    assert client.get("/api/health", headers={"host": "hub.example.com"}).status_code == 200
    assert client.get("/api/health", headers={"host": "other.example.com"}).status_code == 403


def test_changes_from_other_websites_are_refused(client):
    evil = {"origin": "https://evil.example", "host": "hub.home"}
    assert client.post("/api/auth/device", headers=evil).status_code == 403
    fetch = {"sec-fetch-site": "cross-site", "host": "hub.home"}
    assert client.post("/api/auth/device", headers=fetch).status_code == 403
    sandboxed = {"origin": "null", "host": "hub.home"}
    assert client.post("/api/auth/device", headers=sandboxed).status_code == 403
    # Reading is fine (the browser won't let the other site see the answer anyway).
    assert client.get("/api/health", headers=evil).status_code == 200
    own = {"origin": "https://hub.home", "host": "hub.home", "sec-fetch-site": "same-origin"}
    assert client.post("/api/auth/device", headers=own).status_code == 201
