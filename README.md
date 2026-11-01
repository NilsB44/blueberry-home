# Blueberry Home

A self-hosted, ad-free app suite for the home network, built to run on a Raspberry Pi 5 (8 GB).
No logins, one dashboard, many modules: poker tools, file sharing, multiplayer Tetris, network
and security checks and more. See [docs/plan.md](docs/plan.md) for the full roadmap.

**No Pi yet?** Your laptop can stand in for it: it runs the same containers and your phone
connects over Wi-Fi. Step-by-step, plus a tour of what to try: [docs/try-it-now.md](docs/try-it-now.md).

## What works today

- No logins: anyone on the home network can use the hub, and the router is the gate. Each
  device becomes a person the first time it opens the hub, named after what the router calls
  it (e.g. "Nils-iPhone") or the device type ("iPhone", "Pixel 7"), and anyone can change their
  name under **You**. The first device is the admin and the hub's owner. Requests from outside the private address
  ranges are refused (`HUB_TRUSTED_NETWORKS`).
- **Security:** a page only the hub's owner (its first device) can see, with an away-access
  switch (off by default, on for a set time: your own devices on Tailscale can reach the hub,
  but only ones that joined at home, and no ports are opened on the router), signed-in
  devices you can sign out, a security log, login lockout, and a weekly check of the hub and the Pi: refused visitors, wrong
  passwords, new devices, vulnerable packages, open ports, SSH, firewall and updates. See
  [docs/security.md](docs/security.md).
- Devices are remembered by a long-lived cookie (HttpOnly, SameSite=Lax, Secure over HTTPS),
  stored hashed. A browser can't see its MAC address, and phones randomise theirs per network,
  so the cookie is the device's identity: clearing the browser's data makes a new person.
- Dashboard with a tile per module in priority order, games in a folder; drag to rearrange.
- **Poker:** a 13×13 pre-flop chart with raise/fold ranges per seat for heads-up, 6-max and
  full ring (plus raw equity of all 169 hands against 1–9 opponents), an equity calculator for
  any hands and board (exact when possible, Monte Carlo otherwise, from a small Rust engine in
  `engines/poker`) that can also deal random opponents and run out a hand, a play-money pre-flop
  practice game, and a home-game tracker: buy-ins, rebuys, final stacks, the fewest transfers to
  settle up, and lifetime results per player.
- **Files:** a Shared space and a private My files space. Upload from the phone, download on
  the laptop, preview photos and videos, folders, rename, move and delete. See
  [docs/files.md](docs/files.md).
- **Tetris:** solo with a household high-score table, or 2–4 players in a room on the Wi-Fi
  (create one, others join with its four-letter code). Everyone gets the same pieces; clearing
  two or more lines sends garbage to an opponent, last one standing wins. Some pieces carry a ✦
  star: clear its row to collect a power-up (bomb, slow-mo, long bar; in multiplayer also shield
  and rush). Keyboard on computers, buttons and swipes on phones.
- **Network:** whether the internet is up (checked every minute, with uptime and outages), a
  speed test every few hours, how the Pi is doing (temperature, power, memory, disks), and the
  devices on the Wi-Fi with an alert when a new one joins (admins only). The device list needs
  a small scan installed on the Pi: see [docs/network.md](docs/network.md).
- **Trading (owner only):** type in the index levels from your weekly analysis (lower and upper
  level, optionally a stop distance); the hub reads DAX, OMXS30, Nasdaq, S&P 500 and gold prices from IG's API and
  alerts your phone through ntfy when a price comes near a level, with a contrarian trade (short
  coming up from below, long coming down from above), the stop and a position size in contracts
  from your equity and risk %. It also pings you when a new analysis is posted. How often it
  checks, the risk and the alerts are set on its settings page. See [docs/trading.md](docs/trading.md).
- Caddy serves everything over HTTPS on the LAN at `https://hub.home` with its own local CA.
- Installable on phones as a web app (PWA manifest), dark mode follows the system.

## Layout

```
api/        FastAPI + SQLModel + SQLite. Each feature lives in app/modules/<name>/.
engines/    Rust: the poker hand evaluator and equity engine (no dependencies).
web/        SvelteKit (static SPA) + the Caddy config that serves it.
compose.yml Caddy (web) and the API.
docs/       Plan, architecture, Pi setup.
```

## Develop on your laptop

```bash
# API (http://localhost:8000, docs at /api/docs)
cd api
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
HUB_COOKIE_SECURE=false .venv/bin/uvicorn app.main:app --reload

# Web (http://localhost:5173, proxies /api to :8000)
cd web
npm install
npm run dev
```

On Windows (PowerShell) the API commands are:

```powershell
cd api
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
$env:HUB_COOKIE_SECURE="false"; .venv\Scripts\uvicorn app.main:app --reload
```

Running everything with Docker (see [docs/try-it-now.md](docs/try-it-now.md)) avoids
installing Python, Node and Rust at all.

The poker calculator needs the Rust engine: `cargo build --release` in `engines/poker`
(install Rust from https://rustup.rs). The API finds it there automatically.

Tests and checks:

```bash
cd engines/poker && cargo test --release
cd api && .venv/bin/pytest && .venv/bin/ruff check .
cd web && npm run check
```

## Run on the Pi

See [docs/pi-setup.md](docs/pi-setup.md). In short:

```bash
git clone <this repo> hub && cd hub
cp .env.example .env
docker compose up -d
sudo scripts/install-security-check.sh     # the Pi's weekly security check
scripts/update-hub.sh                     # later: pull the latest version and rebuild
```

## Adding a module

1. Create `api/app/modules/<name>/router.py` with an `APIRouter(prefix="/api/<name>")`.
2. Include it in `api/app/main.py` and import its models in `app/db.py:init_db`.
3. Add its entry to `MODULES` in `api/app/modules/__init__.py`.
4. Add `web/src/routes/<path>/+page.svelte`.
