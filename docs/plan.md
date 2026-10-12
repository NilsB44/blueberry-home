# Blueberry Home: Plan

A self-hosted, ad-free, LAN-only app suite running on a **Raspberry Pi 5 (8 GB)**. One login, one dashboard, many small apps ("modules"). Built to be a real engineering project: typed, tested, containerised, observable.

---

## 1. Guiding principles

- **One app, many modules.** A single web app with a shared shell (login, nav, settings) and feature modules behind it. Easier to secure, back up and deploy than ten separate services.
- **Browser first, installable.** A Progressive Web App (PWA) so it works on phone, laptop and tablet, can be "installed" to the home screen, and works offline for lessons.
- **LAN only by default.** Nothing exposed to the internet. Remote access, when you want it, goes through a VPN (WireGuard/Tailscale), never port forwarding.
- **Pi-sized.** Prefer light runtimes and SQLite; keep heavy computation precomputed or in a compiled language.
- **Learn on purpose.** Pick a few technologies you don't use at work to stretch yourself, without making the whole thing exotic.

---

## 2. Hardware and OS

| Item | Recommendation | Why |
|---|---|---|
| Board | Pi 5, 8 GB | Already chosen. Plenty for this stack. |
| Storage | **NVMe SSD via M.2 HAT** (256–512 GB) | SD cards wear out under database writes; NVMe is far faster and more reliable. Boot from it. |
| Cooling | Official Active Cooler | Pi 5 throttles without it under sustained load (e.g. poker sims). |
| Power | Official 27 W USB-C PSU | Under-powered Pi 5s throttle and can't power NVMe reliably. |
| Backup disk | Any USB drive, or a cloud bucket | For nightly encrypted backups. |
| OS | Raspberry Pi OS Lite (64-bit, Bookworm) or Ubuntu Server 24.04 | Headless, 64-bit is required for most container images. |

---

## 3. Architecture

```
            Phone / Laptop / Tablet (browser, installable PWA)
                              │  HTTPS (local CA cert)
                              ▼
   ┌───────────────────── Raspberry Pi 5 ─────────────────────┐
   │  Caddy (reverse proxy, TLS, https://hub.home)             │
   │     │                                                     │
   │     ├── Web frontend (static PWA build)                   │
   │     ├── API server  ── REST + WebSockets                  │
   │     │     modules: lang, poker, files, games, plants,     │
   │     │              finance, reading, ...                  │
   │     │     ├── SQLite (WAL mode)  ── app data              │
   │     │     └── Background jobs (scheduler)                 │
   │     ├── Poker engine (Rust, called by API)                │
   │     ├── File sharing service (see §5.3)                   │
   │     └── Optional: Ollama (small local LLM), Jellyfin, ... │
   │  Pi-hole / AdGuard Home (DNS + local names)               │
   │  WireGuard / Tailscale (remote access)                    │
   │  Uptime Kuma / Grafana (monitoring)                       │
   │  restic (encrypted nightly backups)                       │
   └───────────────────────────────────────────────────────────┘
       everything runs in Docker Compose, one file
```

### Recommended stack

| Layer | Pick | Alternatives | Notes |
|---|---|---|---|
| Frontend | **SvelteKit** (or React + Vite) + TypeScript + Tailwind | Next.js | SvelteKit is small and fast on cheap phones; React if you'd rather go with what you know. Build as a static PWA. |
| Backend API | **Python + FastAPI** | Go, Node (Fastify) | FastAPI is pleasant, typed (Pydantic), great for the data-heavy modules (finance, stats). Go if you want a single tiny binary. |
| Realtime | WebSockets (FastAPI native) | Socket.IO | Needed for Tetris and live poker home-game tables. |
| Database | **SQLite** (WAL) via SQLAlchemy/SQLModel + Alembic migrations | Postgres | One user household, SQLite is ideal on a Pi. Move to Postgres only if you outgrow it. |
| Compute-heavy code | **Rust** (poker equity engine) exposed via PyO3 or a small HTTP service | C++, NumPy | A great "learn something new" piece, and the poker solver is where speed matters. |
| Auth | Local accounts, Argon2 password hashing, session cookies; optional **Authelia** for SSO + 2FA across all services | Authentik (heavier) | |
| Reverse proxy / TLS | **Caddy** with an internal CA | Traefik, nginx | Gives you `https://hub.home` with a cert trusted on your devices. |
| Containers | **Docker Compose** | Podman | One `compose.yml`, `docker compose up -d`. Use multi-arch (arm64) images. |
| CI/CD | GitHub Actions builds arm64 images, Pi pulls them (Watchtower or a deploy script) | Build on the Pi | Building Rust on the Pi is slow; cross-build in CI. |
| Testing | pytest, Vitest, Playwright | | Fintech habits apply: tests on the poker maths and payout logic especially. |

---

## 4. Phased roadmap

Each phase ends with something usable. Rough sizes assume evenings/weekends.

### Phase 0: Foundations (1–2 weekends)
- Flash OS, boot from NVMe, SSH keys only, firewall (`ufw`), unattended security updates.
- Docker + Compose, Caddy with local HTTPS, Pi-hole/AdGuard for `hub.home` DNS.
- Monorepo skeleton: `frontend/`, `api/`, `engines/poker/`, `infra/compose.yml`.
- App shell: login, user profiles (you + guests), dashboard of module tiles, dark mode.
- Nightly `restic` backup of the SQLite DB and file shares; test a restore once.
- Uptime Kuma for "is everything up".

### Phase 1: French learning MVP (the first real module)
- **Content model:** Course → Unit → Lesson → Exercise. Lessons are YAML/JSON files in the repo so you can author and version them.
- **Exercise types:** multiple choice, translate (EN→FR and FR→EN), word bank / tap-to-build sentence, match pairs, listening (type what you hear), fill the gap with verb conjugation.
- **Spaced repetition:** an **FSRS** scheduler (the modern Anki algorithm) for vocabulary and sentences. Every word you meet becomes a review card.
- **Answer checking:** accent-tolerant matching (accept "a" for "à" with a gentle hint), multiple accepted translations.
- **Audio:** text-to-speech with **Piper** (runs locally on a Pi, has decent French voices). Pre-generate audio for lesson content at build time.
- **Motivation, minus the dark patterns:** streaks with freezes, daily XP goal, simple stats. No hearts, no ads, no guilt notifications.
- **Content to start:** A1→A2 aligned to CEFR: greetings, numbers, café/restaurant, travel, work talk, passé composé vs imparfait later. Import a frequency list for the top ~2,000 French words as the vocab backbone.

### Phase 2: Poker toolkit v1
- **Pre-flop equity tables:** all 169 starting hands, equity vs 1–8 random opponents, plus hand vs hand and hand vs range. Precompute with the Rust engine (exhaustive for heads-up, Monte Carlo for multiway) and store in SQLite so lookups are instant.
- **Range grid UI:** the classic 13×13 matrix, colour-coded by equity; click a hand for details; select a range by dragging.
- **Equity calculator:** any hands + any board (flop/turn/river) → equity, with Monte Carlo running in Rust in under a second.
- **Home game manager:**
  - Session setup: players, buy-ins, rebuys/add-ons, blinds.
  - **Cash game settle-up:** enter final stacks → minimal set of transfers ("Alex pays Sam $40"). This is a min-cash-flow problem, nice and fintech-flavoured.
  - **Tournament payouts:** configurable payout structures (e.g. 50/30/20), ICM calculator for deal-making.
  - Blind timer that you can cast to a TV, with level alerts.
  - Player ledger across sessions: lifetime results, graphs, leaderboards.
- Later in Phase 4: post-flop tools (see §6).

### Phase 3: Network and file sharing
- **File sharing:** don't reinvent this. Run a proven service and link it from the dashboard:
  - **Samba** shares for "just a network drive" on laptops,
  - plus **FileBrowser** (light web UI) or **Nextcloud** (heavy, full-featured; probably overkill on a Pi). Recommendation: Samba + FileBrowser.
  - **Syncthing** for phone photo backup and folder sync.
  - A small built-in "drop zone": send a file or link from phone to laptop instantly (like AirDrop for the LAN).
- **Secure networking:**
  - **Pi-hole/AdGuard Home:** network-wide ad and tracker blocking, local DNS names. Fits your "no ads" theme across every device.
  - **WireGuard (via wg-easy) or Tailscale:** reach the hub safely from outside the house. Tailscale is the easiest.
  - **Network dashboard:** devices currently on the Wi-Fi (via ARP scan / router API), alerts on unknown devices, DNS query stats.
  - Hardening checklist in the repo: SSH keys only, fail2ban, automatic updates, least-privilege containers, secrets in `.env` not git.

### Phase 4: Multiplayer Tetris
- Canvas-based client, game logic shared between server and client (TypeScript, or Rust → WASM if you want a stretch).
- Implement the modern guideline rules: 7-bag randomiser, SRS rotation, hold piece, ghost piece.
- **Server-authoritative multiplayer over WebSockets:** lobby, 2–4 players, garbage lines sent on multi-line clears, KO mode.
- Leaderboards, replays (store input logs, replay deterministically from the seed).
- Same realtime plumbing later powers poker home-game tables or a quiz game.

### Phase 5: Mandarin (for Singapore)
- In Singapore, **English** is the main working language and **Mandarin** is the most widely taught mother tongue; Singlish and Hokkien are common colloquially, and Malay is the national language. Mandarin is the sensible second course.
- Mandarin-specific needs the French module won't have:
  - **Pinyin with tones**, tone-mark input (type `ni3 hao3` → nǐ hǎo).
  - **Tone drills:** listen and pick the tone; minimal pairs.
  - **Hanzi:** simplified characters (Singapore uses simplified), stroke order animation via the open-source **Hanzi Writer** library, radicals, character → word decomposition.
  - **HSK-aligned** vocabulary (HSK 1–3 first), using the open **CC-CEDICT** dictionary.
  - Singapore-flavoured content: hawker centre ordering, MRT, housing, workplace phrases.
- Because Phase 1 built a generic course engine, this is mostly content plus a few new exercise types.

---

## 5. Extra feature ideas, picked for you

Ranked roughly by value for effort. Each is a module in the same app.

### Finance (fintech/regtech brain)
1. **Personal finance dashboard:** import bank CSVs, auto-categorise, budgets, net worth over time. Plan for SGD and multi-currency now since you're moving. All data stays on the Pi.
2. **Portfolio tracker:** holdings, cost basis, allocation, dividends; prices pulled on a schedule. Add Singapore specifics later: CPF, SRS, SGX tickers, SSBs and T-bills.
3. **Relocation calculator:** salary after Singapore tax vs current location, rent/cost-of-living comparison, savings rate. Pure maths, very quick to build.
4. **Poker bankroll tracker** that ties into the home-game ledger (hourly rate, variance, drawdown charts): finance meets poker.
5. Option: self-host **Firefly III** or **Actual Budget** instead of building the budgeting part, and spend your build time on the novel bits.

### Learning and reading
6. **Reading tracker:** books (ISBN lookup via Open Library), progress, notes, quotes, yearly goals.
7. **Highlight → flashcard pipeline:** paste a quote or concept from a book or YouTube video, it becomes an FSRS review card using the same engine as the language app. One review queue for everything you're studying.
8. **Graded reader for French:** paste a French article, it highlights words you don't know yet (from your SRS history) and lets you tap to translate and add them as cards.
9. **YouTube study log:** save videos with notes and timestamps; pull the transcript and make cards from it. Optional French/Mandarin YouTube lists by level.
10. **Self-hosted e-book library:** Calibre-Web or Kavita for your ebooks, readable from any device.

### Plants
11. **Plant care tracker:** each plant has a photo, species, watering/fertilising schedule, and a log. Reminders on the dashboard.
12. **Sensors (hardware fun):** cheap soil-moisture sensors with an ESP32 over Wi-Fi (MQTT to the Pi), or temperature/humidity sensors. Graph it, alert when dry. Singapore humidity makes this interesting for indoor plants.
13. Growth timeline: monthly photo per plant, auto-made timelapse.

### Gaming (WoW and general)
14. **WoW companion:** the Blizzard API has character, gear, Mythic+ and raid data. Track your characters, weekly vault progress, M+ scores; pull **Raider.IO / Warcraft Logs** for performance. A "weekly reset checklist" per character.
15. **Gold / auction-house tracker:** the AH API gives commodity prices; chart prices and spot flips. It's basically a market data feed, which suits a finance engineer.
16. **LAN game nights:** besides Tetris, simple party games (quiz, Codenames-style word game) reusing the WebSocket lobby.

### Home and utilities
17. **Media server:** Jellyfin for your own videos/music (direct play only; the Pi 5 has no hardware video encoder so avoid heavy transcoding).
18. **Password manager:** Vaultwarden (self-hosted Bitwarden), behind the VPN. Very popular, very light.
19. **Notes / wiki:** a simple markdown notes module, or self-host something like Memos or Trilium.
20. **Local AI assistant (optional):** **Ollama** with a small model (e.g. a 1–3B parameter model) runs on the Pi 5 8 GB at a slow but usable speed. Uses: explain a French grammar error, generate example sentences, summarise notes. Treat it as a nice-to-have; keep core features working without it.
21. **Household board:** shared shopping list, chores, calendar, if you live with others.

---

## 6. Poker roadmap beyond pre-flop

- Post-flop equity with board textures and outs/odds trainer ("how many outs? what's the % to hit?") quizzes.
- **Push/fold charts** for short-stack tournament play (Nash equilibrium tables, computed once).
- **Pot odds and EV trainer:** flashcard-style drills using the same SRS engine.
- Hand history import (from online sites) and replayer.
- Simplified **GTO solving** for small spots (e.g. heads-up river) via counterfactual regret minimisation (CFR) in Rust. Full-tree solvers like PioSolver need far more RAM and CPU than a Pi, so keep scope to small abstract games and river spots. This is a fantastic learning project in itself.

---

## 7. What the Pi 5 can and can't comfortably do

| Comfortable | Possible with care | Avoid / offload |
|---|---|---|
| Web app + API + SQLite for a household | Monte Carlo equity (Rust, multi-core) | Full multi-street GTO solvers |
| WebSocket games for 2–8 players | Small local LLM (1–3B) at a few tokens/sec | Video transcoding for streaming |
| Pi-hole, VPN, Samba, Syncthing | Piper TTS on the fly (pre-generate instead) | Large LLMs (7B+ is slow) |
| Background jobs, price fetches, backups | Nextcloud (heavy but works) | Building big Rust/Docker images on-device |

Rules of thumb: precompute what you can (equity tables, TTS audio), cache API data, use SQLite WAL, keep total RAM use under ~5 GB so the system stays snappy.

---

## 8. Engineering setup worth doing early

- **Monorepo on GitHub** with a README, `compose.yml`, and an `ARCHITECTURE.md`.
- **Module pattern:** each module owns its API router, DB tables, migrations and frontend routes, so new features are mostly copy-the-pattern.
- **CI:** lint + tests on every push; build arm64 images; tag releases.
- **Observability:** structured logs, a `/health` endpoint per module, Uptime Kuma alerts to your phone (ntfy or Telegram).
- **Secrets and data:** `.env` files never committed; DB and uploads on the NVMe; restic to an external drive plus an offsite copy.
- **Dev loop:** develop on your laptop with the same Compose file; deploy to the Pi with `git pull && docker compose up -d` or via CI.

---

## 9. Suggested order, in one line each

1. Phase 0 foundations and app shell.
2. French course engine + FSRS + Piper audio.
3. Poker pre-flop tables, equity calculator, home-game settle-up.
4. Pi-hole, Tailscale, Samba + FileBrowser, Vaultwarden.
5. Multiplayer Tetris.
6. Mandarin course.
7. Then pick from: finance dashboard, WoW companion, plant tracker with sensors, reading + unified review queue.

## 10. Open questions for you

- Frontend: SvelteKit (new to learn) or React (familiar)? Default in this plan: **SvelteKit**.
- Backend: Python/FastAPI or Go? Default: **FastAPI**, with Rust for the poker engine.
- Who else uses it? Just you, or housemates and poker friends as guest accounts? Default: **you plus guest accounts**.
- Want a GitHub repo set up and a Phase 0 skeleton written next?
