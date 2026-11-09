ECONOMY = {
    "accounts": [
        {"name": "Savings", "kind": "cash", "balance": 50000},
        {"name": "Mortgage", "kind": "loan", "balance": 1200000},
    ],
    "subscriptions": [{"name": "Spotify", "price": 129, "period": "month"}],
    "rules": {"wait_days": 7, "max_net_worth_pct": 2, "monthly_expenses": 15000},
    "wishlist": [
        {"name": "Headphones", "price": 3000, "added": "2026-11-01", "checks": {"need": True}}
    ],
}


def test_starts_empty_with_default_rules(admin_client):
    e = admin_client.get("/api/economy").json()
    assert e["accounts"] == e["subscriptions"] == e["wishlist"] == []
    assert e["rules"]["wait_days"] == 7
    assert e["rules"]["big_wait_days"] == 30


def test_round_trips(admin_client):
    assert admin_client.put("/api/economy", json=ECONOMY).status_code == 200
    e = admin_client.get("/api/economy").json()
    assert e["accounts"] == ECONOMY["accounts"]
    assert e["wishlist"][0]["checks"] == {"need": True}
    assert e["rules"]["max_net_worth_pct"] == 2
    # Rules left out keep their defaults.
    assert e["rules"]["big_price"] == 5000


def test_shape_is_checked(admin_client):
    bad_kind = {"accounts": [{"name": "X", "kind": "crypto", "balance": 1}]}
    assert admin_client.put("/api/economy", json=bad_kind).status_code == 422
    negative = {"subscriptions": [{"name": "X", "price": -1, "period": "month"}]}
    assert admin_client.put("/api/economy", json=negative).status_code == 422
    too_many = {"wishlist": [{"name": "X", "price": 1, "added": "2026-11-01"}] * 101}
    assert admin_client.put("/api/economy", json=too_many).status_code == 422


def test_only_for_the_owner(admin_client):
    tiles = {m["id"]: m for m in admin_client.get("/api/modules").json()}
    assert tiles["economy"]["owner_only"] is True
    admin_client.put("/api/economy", json=ECONOMY)
    admin_client.cookies.clear()
    admin_client.post("/api/auth/device")
    assert "economy" not in {m["id"] for m in admin_client.get("/api/modules").json()}
    assert admin_client.get("/api/economy").status_code == 403
    assert admin_client.put("/api/economy", json=ECONOMY).status_code == 403


def test_needs_a_person(client):
    assert client.get("/api/economy").status_code == 401
