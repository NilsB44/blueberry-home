from tests.conftest import ADMIN


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
    assert admin_client.get("/api/users").status_code == 403


def test_modules_requires_login(client):
    assert client.get("/api/modules").status_code == 401


def test_modules_lists_tiles(admin_client):
    ids = [m["id"] for m in admin_client.get("/api/modules").json()]
    assert ids[:3] == ["french", "mandarin", "assistant"]
    assert "poker" in ids
    assert {"french", "poker", "tetris", "mandarin"} <= set(ids)
