from tests.conftest import IPHONE_UA

LAYOUT = {
    "items": [
        {"type": "folder", "id": "games", "name": "Games", "apps": ["tetris", "poker"]},
        {"type": "app", "id": "files"},
    ]
}


def test_every_module_starts_in_a_folder(admin_client):
    modules = admin_client.get("/api/modules").json()
    assert {m["folder"] for m in modules} <= {"games", "learning", "nerd", "life"}
    folder = {m["id"]: m["folder"] for m in modules}
    assert folder["tetris"] == folder["poker"] == "games"
    assert folder["french"] == "learning"


def test_layout_is_empty_until_saved(admin_client):
    assert admin_client.get("/api/home/layout").json() is None


def test_layout_round_trips_and_resets(admin_client):
    assert admin_client.put("/api/home/layout", json=LAYOUT).status_code == 200
    assert admin_client.get("/api/home/layout").json() == LAYOUT
    assert admin_client.delete("/api/home/layout").status_code == 204
    assert admin_client.get("/api/home/layout").json() is None


def test_layout_is_per_person(admin_client):
    admin_client.put("/api/home/layout", json=LAYOUT)
    admin_client.post("/api/auth/logout")
    admin_client.cookies.clear()
    admin_client.post("/api/auth/device", headers={"user-agent": IPHONE_UA})
    assert admin_client.get("/api/home/layout").json() is None


def test_layout_shape_is_checked(admin_client):
    bad = {"items": [{"type": "folder", "id": "x", "name": "", "apps": []}]}
    assert admin_client.put("/api/home/layout", json=bad).status_code == 422
    bad = {"items": [{"type": "widget", "id": "x"}]}
    assert admin_client.put("/api/home/layout", json=bad).status_code == 422
    huge = {"items": [{"type": "app", "id": str(i)} for i in range(201)]}
    assert admin_client.put("/api/home/layout", json=huge).status_code == 422


def test_layout_needs_a_person(client):
    assert client.get("/api/home/layout").status_code == 401
    assert client.put("/api/home/layout", json=LAYOUT).status_code == 401
