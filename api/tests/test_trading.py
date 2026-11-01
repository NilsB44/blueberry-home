import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlmodel import Session

from app import db as db_module
from app.config import get_settings
from app.modules.trading import watcher
from app.modules.trading.models import TradingLevel
from app.modules.trading.watcher import TradingSettings

NTFY = "https://ntfy.example/topic"
FEED = "https://analyses.example/feed/"
DAX_EPIC = "IX.D.DAX.IFD.IP"


def feed(*items: tuple[str, str, str]) -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>https://analyses.example/{g}</link><guid>{g}</guid>"
        f"<category>{c}</category></item>"
        for g, t, c in items
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{body}</channel></rss>'.encode()


class FakeWorld:
    """IG, ntfy and the feed, answered in memory."""

    def __init__(self) -> None:
        self.bid = 25_690.0
        self.offer = 25_692.0
        self.market_status = "TRADEABLE"
        self.logins = 0
        self.expire_session = False
        self.reject_login = False
        self.pushes: list[httpx.Request] = []
        self.feed = feed(("1", "Old analysis", "Marknadsanalys"))

    def handle(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(NTFY):
            self.pushes.append(request)
            return httpx.Response(200, json={})
        if url.startswith(FEED):
            return httpx.Response(200, content=self.feed)
        assert request.headers["X-IG-API-KEY"] == "key"
        if request.url.path.endswith("/session"):
            if self.reject_login:
                return httpx.Response(401, json={"errorCode": "error.security.invalid-details"})
            assert json.loads(request.content) == {"identifier": "nils", "password": "pw"}
            self.logins += 1
            return httpx.Response(
                200, headers={"CST": f"cst{self.logins}", "X-SECURITY-TOKEN": "tok"}, json={}
            )
        if request.url.path.endswith("/markets"):
            if self.expire_session:
                self.expire_session = False
                return httpx.Response(401, json={"errorCode": "error.security.token-invalid"})
            assert request.headers["CST"] == f"cst{self.logins}"
            if "searchTerm" in request.url.params:
                return httpx.Response(
                    200,
                    json={
                        "markets": [
                            {
                                "epic": DAX_EPIC,
                                "instrumentName": "Germany 40",
                                "instrumentType": "INDICES",
                                "expiry": "-",
                                "bid": self.bid,
                                "offer": self.offer,
                            }
                        ]
                    },
                )
            assert request.url.params["epics"] == DAX_EPIC
            return httpx.Response(
                200,
                json={
                    "marketDetails": [
                        {
                            "instrument": {"epic": DAX_EPIC, "name": "Germany 40"},
                            "snapshot": {
                                "bid": self.bid,
                                "offer": self.offer,
                                "marketStatus": self.market_status,
                            },
                        }
                    ]
                },
            )
        return httpx.Response(404)


@pytest.fixture
def world(monkeypatch):
    w = FakeWorld()
    monkeypatch.setenv("HUB_IG_API_KEY", "key")
    monkeypatch.setenv("HUB_IG_USERNAME", "nils")
    monkeypatch.setenv("HUB_IG_PASSWORD", "pw")
    get_settings.cache_clear()
    monkeypatch.setattr(
        watcher, "make_client", lambda: httpx.Client(transport=httpx.MockTransport(w.handle))
    )
    return w


SETTINGS = {
    **TradingSettings().model_dump(),
    "enabled": True,
    "ntfy_url": NTFY,
    "feed_url": FEED,
    "near_points": 10,
    "equity": 250_000,
    "risk_pct": 1,
    "instruments": [{"name": "DAX", "epic": DAX_EPIC}, {"name": "OMXS30", "epic": ""}],
}

SHORT = {
    "instrument": "DAX",
    "bias": "short",
    "entry_low": 25_700,
    "entry_high": 25_650,
    "stop": 25_780,
    "targets": "25400, 25200",
}


@pytest.fixture
def trader(admin_client, world):
    assert admin_client.put("/api/trading/settings", json=SETTINGS).status_code == 200
    return admin_client


def test_tile_is_ready_and_only_for_the_owner(admin_client):
    tiles = {m["id"]: m for m in admin_client.get("/api/modules").json()}
    assert tiles["trading"]["status"] == "ready"
    assert tiles["trading"]["owner_only"] is True
    admin_client.cookies.clear()
    admin_client.post("/api/auth/device")
    assert "trading" not in {m["id"] for m in admin_client.get("/api/modules").json()}
    assert admin_client.get("/api/trading/settings").status_code == 403


def test_settings_have_defaults_and_are_checked(admin_client):
    s = admin_client.get("/api/trading/settings").json()
    assert s["enabled"] is False
    assert s["price_check_seconds"] == 60
    assert s["feed_url"] == "https://mikrittrading.com/feed/"
    assert [i["name"] for i in s["instruments"]][:2] == ["DAX", "OMXS30"]

    too_fast = {**s, "price_check_seconds": 5}
    assert admin_client.put("/api/trading/settings", json=too_fast).status_code == 422
    twice = {**s, "instruments": [{"name": "DAX"}, {"name": "dax"}]}
    assert admin_client.put("/api/trading/settings", json=twice).status_code == 422

    changed = {**s, "price_check_seconds": 30, "risk_pct": 0.5, "feed_check_minutes": 60}
    assert admin_client.put("/api/trading/settings", json=changed).status_code == 200
    again = admin_client.get("/api/trading/settings").json()
    assert (again["price_check_seconds"], again["risk_pct"], again["feed_check_minutes"]) == (
        30,
        0.5,
        60,
    )


def test_levels_need_a_known_instrument_and_a_stop_on_the_right_side(trader):
    assert trader.post("/api/trading/levels", json={**SHORT, "stop": 25_600}).status_code == 422
    long = {**SHORT, "bias": "long", "stop": 25_660}
    assert trader.post("/api/trading/levels", json=long).status_code == 422
    ftse = {**SHORT, "instrument": "FTSE"}
    assert trader.post("/api/trading/levels", json=ftse).status_code == 422

    level = trader.post("/api/trading/levels", json=SHORT).json()
    # The zone is stored low to high.
    assert (level["entry_low"], level["entry_high"]) == (25_650, 25_700)
    # Before there's a price: 2,500 risked over the 105 points from the zone's middle to the stop.
    assert level["size_per_point"] == pytest.approx(2500 / 105, abs=0.01)

    single = trader.post(
        "/api/trading/levels", json={**SHORT, "entry_low": 25_700, "entry_high": None}
    ).json()
    assert single["entry_high"] == 25_700


def test_size_per_point():
    s = TradingSettings(equity=250_000, risk_pct=1)
    assert watcher.size_per_point(s, 25_700, 25_780) == 31.25
    assert watcher.size_per_point(s, 25_700, 25_700) is None


def test_price_near_a_level_alerts_once_with_the_stop_and_size(trader, world):
    trader.post("/api/trading/levels", json=SHORT)
    world.bid, world.offer = 25_630, 25_632  # 19 points below the zone: quiet

    status = trader.post("/api/trading/check").json()
    assert status["price_error"] == ""
    assert status["prices"][0]["mid"] == 25_631
    assert trader.get("/api/trading/alerts").json() == []

    world.bid, world.offer = 25_640, 25_642  # 9 points away
    trader.post("/api/trading/check")
    alerts = trader.get("/api/trading/alerts").json()
    assert len(alerts) == 1
    a = alerts[0]
    assert a["kind"] == "level" and a["delivered"] is True and a["price"] == 25_641
    # Entering at the bottom of the zone, 130 points from the stop: 2,500 / 130.
    assert "stop 25,780 (130 pts)" in a["message"]
    assert "Size 19.23 per point risks 2,500 (1% of 250,000)" in a["message"]
    push = world.pushes[-1]
    assert push.headers["Priority"] == "high"
    assert push.content.decode() == a["message"]

    # Still near: the cooldown keeps it quiet.
    trader.post("/api/trading/check")
    assert len(trader.get("/api/trading/alerts").json()) == 1
    level = trader.get("/api/trading/levels").json()[0]
    assert level["distance"] == 9 and level["last_alert_at"]


def test_cooldown_ends_and_closed_markets_and_old_levels_stay_quiet(trader, world):
    level_id = trader.post("/api/trading/levels", json=SHORT).json()["id"]
    world.bid, world.offer = 25_660, 25_662

    world.market_status = "CLOSED"
    trader.post("/api/trading/check")
    assert trader.get("/api/trading/alerts").json() == []

    world.market_status = "TRADEABLE"
    trader.post("/api/trading/check")
    assert len(trader.get("/api/trading/alerts").json()) == 1

    with Session(db_module.get_engine()) as s:
        level = s.get(TradingLevel, level_id)
        level.last_alert_at = datetime.now(UTC) - timedelta(minutes=241)
        s.add(level)
        s.commit()
    trader.post("/api/trading/check")
    assert len(trader.get("/api/trading/alerts").json()) == 2

    with Session(db_module.get_engine()) as s:
        level = s.get(TradingLevel, level_id)
        level.last_alert_at = None
        level.valid_until = date.today() - timedelta(days=2)
        s.add(level)
        s.commit()
    trader.post("/api/trading/check")
    assert len(trader.get("/api/trading/alerts").json()) == 2


def test_paused_levels_stay_quiet_and_can_be_deleted(trader, world):
    level_id = trader.post("/api/trading/levels", json=SHORT).json()["id"]
    world.bid, world.offer = 25_660, 25_662
    paused = trader.patch(f"/api/trading/levels/{level_id}", json={"active": False})
    assert paused.json()["active"] is False
    trader.post("/api/trading/check")
    assert trader.get("/api/trading/alerts").json() == []
    assert trader.delete(f"/api/trading/levels/{level_id}").status_code == 204
    assert trader.get("/api/trading/levels").json() == []


def test_an_expired_ig_session_logs_in_again(trader, world):
    trader.post("/api/trading/check")
    assert world.logins == 1
    world.expire_session = True
    status = trader.post("/api/trading/check").json()
    assert status["price_error"] == "" and world.logins == 2


def test_a_failed_login_is_not_retried_straight_away(trader, world):
    world.reject_login = True
    status = trader.post("/api/trading/check").json()
    assert "error.security.invalid-details" in status["price_error"]
    world.reject_login = False
    status = trader.post("/api/trading/check").json()
    assert "trying again in a few minutes" in status["price_error"]
    assert world.logins == 0


def test_without_ig_keys_the_page_says_so(admin_client, monkeypatch):
    offline = httpx.MockTransport(lambda r: httpx.Response(503))
    monkeypatch.setattr(watcher, "make_client", lambda: httpx.Client(transport=offline))
    status = admin_client.get("/api/trading/status").json()
    assert status["ig_configured"] is False and status["ig_demo"] is True
    status = admin_client.post("/api/trading/check").json()
    assert "HUB_IG_API_KEY" in status["price_error"]
    assert "feed" in status["feed_error"]


def test_instruments_without_an_ig_market_are_pointed_out(trader):
    settings = {**SETTINGS, "instruments": [{"name": "DAX", "epic": ""}]}
    trader.put("/api/trading/settings", json=settings)
    assert "settings page" in trader.post("/api/trading/check").json()["price_error"]


def test_market_search_finds_epics(trader):
    found = trader.get("/api/trading/markets", params={"q": "Germany 40"}).json()
    assert found[0]["epic"] == DAX_EPIC and found[0]["name"] == "Germany 40"


def test_new_posts_on_the_feed_are_pinged_after_the_first_read(trader, world):
    trader.post("/api/trading/check")
    # The first read is the starting point.
    assert trader.get("/api/trading/alerts").json() == []

    world.feed = feed(
        ("3", "Veckoanalys v45", "PremiumMarknadsanalys"),
        ("2", "DAX idag", "Marknadsanalys"),
        ("1", "Old analysis", "Marknadsanalys"),
    )
    trader.post("/api/trading/check")
    alerts = trader.get("/api/trading/alerts").json()
    assert [(a["title"], a["message"]) for a in alerts] == [
        ("New premium analysis", "Veckoanalys v45"),
        ("New analysis", "DAX idag"),
    ]
    assert alerts[0]["link"] == "https://analyses.example/3"
    assert world.pushes[-1].headers["Click"] == "https://analyses.example/3"

    trader.post("/api/trading/check")
    assert len(trader.get("/api/trading/alerts").json()) == 2


def test_test_alert_without_ntfy_is_kept_in_the_hub(admin_client, world):
    alert = admin_client.post("/api/trading/test-alert").json()
    assert alert["delivered"] is False and "ntfy" in alert["error"]
    assert admin_client.get("/api/trading/alerts").json()[0]["kind"] == "test"


def test_watcher_does_nothing_while_switched_off(admin_client, world):
    watcher.tick()
    assert world.logins == 0 and watcher.state.price_checked_at is None
