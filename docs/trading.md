# Trading

An owner-only page that watches index prices against levels you type in, and tells your phone
when a price comes near one. It never places trades.

## How it works

1. After the weekend analysis, add each level on **Trading**: the market and the level's lower
   and upper price. Optionally, how many points beyond it your stop goes, which adds a position
   size to alerts. Levels stay until you delete or pause them.
2. The hub reads prices from IG's REST API, every 60 seconds by default, in one request for all
   markets. When a market is open and its price is within *N* points of a level's entry zone
   (or inside it), you get an alert with the trade (and the stop and a position size, if you gave a stop), and the level
   then stays quiet for the cooldown.
3. The trade is **contrarian, decided when the price gets there**: coming up to the level from
   below is a short with the stop above the zone; coming down from above is a long with the
   stop below it. Inside the zone, the edge the price is nearer counts as where it came from.
   So one level works both ways, e.g. resistance that later becomes support.
4. It reads the analysis site's RSS feed (`https://mikrittrading.com/feed/` by default) every
   30 minutes and pings you about new posts; premium posts show up by title even when the
   content is for members. The first read only remembers what's already there.

Everything above (on/off, how often, how close, the cooldown, equity and risk %, the ntfy topic,
the feed and the markets) is on **Trading → Settings**. Only IG's credentials live in `.env`.

**Position size** is in contracts: `equity × risk % ÷ (|entry − stop| × point value)`, entering at
the nearest edge of the zone. The point value is what one point is worth per contract in your
equity's currency, set per market in Settings. IG shows it on the market's info page: Tyskland 40
Micro says "En punkt är värd EUR 1 (SEK 10.96)", so enter 10.96. The number is the contracts
to enter.

## Setting up IG

1. On IG, open **My Account → Settings → API keys** and make a key. A key for a **demo** account
   (same email as your live account) is the safe choice: the hub only reads prices, and a leaked
   demo key can't touch real money. Demo prices follow the same feed as live.
2. Add to `.env` on the Pi, then `docker compose up -d`:
   ```
   HUB_IG_API_KEY=...
   HUB_IG_USERNAME=...
   HUB_IG_PASSWORD=...
   HUB_IG_DEMO=true
   ```
3. On **Trading → Settings → Markets**, press **Find** next to each market and pick IG's market
   (e.g. "Germany 40" for DAX, "Sweden 30" for OMXS30, "US Tech 100", "US 500", "Spot Gold").
   Pick the cash/daily one rather than a futures month.
4. Press **Check now** on the Trading page to see prices.

IG's limits: 30 price requests a minute per account (so 15 seconds is the shortest interval),
and accounts get locked after repeated failed logins, so after a failed login the hub waits
15 minutes before trying again.

## Alerts on your phone (ntfy)

Install the [ntfy](https://ntfy.sh) app, subscribe to a topic with a long random name, and paste
`https://ntfy.sh/<that-name>` into the settings. **Send a test alert** checks it. Anyone who knows
the topic name can read it, so keep it random. You can also run ntfy on the Pi and use its URL.
Without a topic, alerts still appear on the Trading page.

## Testing without the market open

`api/tests/test_trading.py` runs the watcher against a fake IG, ntfy and feed: levels, the
cooldown, closed markets, expired levels, re-login and the feed. With real keys, **Check now**
reads prices immediately even while the watcher is switched off.
