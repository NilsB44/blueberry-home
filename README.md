# Blueberry Home

A self-hosted, ad-free app suite for the home network, built to run on a Raspberry Pi 5 (8 GB).
One login, one dashboard, many modules: language learning, poker tools, file sharing, multiplayer
Tetris, a local AI assistant and more. See [docs/plan.md](docs/plan.md) for the full roadmap.

**No Pi yet?** Your laptop can stand in for it: it runs the same containers and your phone
connects over Wi-Fi. Step-by-step, plus a tour of what to try: [docs/try-it-now.md](docs/try-it-now.md).

## What works today

- First-run setup creates the admin account; admins can add guest accounts.
- Session cookies (HttpOnly, SameSite=Lax, Secure over HTTPS), Argon2 password hashing,
  session tokens stored hashed.
- Dashboard with a tile per module; planned modules show which phase they land in.
- **French:** A1 lessons (greetings, café, numbers, introductions, work) with multiple choice,
  translation, word-bank, matching, listening and fill-the-gap exercises. Answers are checked
  forgivingly (missing accents and one-letter typos count, with a correction). Every word you
  meet goes into spaced-repetition reviews (FSRS). XP, daily goal and streaks, no ads.
- **Poker:** a 13×13 pre-flop chart (equity of all 169 hands against 1–9 opponents), an
  equity calculator for any hands and board (exact when possible, Monte Carlo otherwise, from a
  small Rust engine in `engines/poker`), and a home-game tracker: buy-ins, rebuys, final stacks,
  the fewest transfers to settle up, and lifetime results per player.
- **Mandarin:** an HSK 1 unit with a Singapore flavour (greetings, numbers, introductions,
  ordering at a hawker centre). Type answers as characters or pinyin (tone marks or numbers;
  missing tones get a gentle nudge) and draw characters stroke by stroke.
- **Files:** a Shared space and a private My files space. Upload from the phone, download on
  the laptop, preview photos and videos, folders, rename, move and delete. See
  [docs/files.md](docs/files.md).
- **Assistant:** chat with a small local language model through Ollama, streamed token by token.
- Caddy serves everything over HTTPS on the LAN at `https://hub.home` with its own local CA.
- Installable on phones as a web app (PWA manifest), dark mode follows the system.

## Layout

```
api/        FastAPI + SQLModel + SQLite. Each feature lives in app/modules/<name>/.
engines/    Rust: the poker hand evaluator and equity engine (no dependencies).
web/        SvelteKit (static SPA) + the Caddy config that serves it.
compose.yml Caddy (web), API, and Ollama (opt-in "llm" profile).
docs/       Plan, architecture, Pi setup, local LLM notes.
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

The assistant needs Ollama. Install it on your laptop (`ollama pull qwen3:4b`) and start the
API with `HUB_OLLAMA_URL=http://localhost:11434`.

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
docker compose up -d                      # hub only
docker compose --profile llm up -d        # hub + local language model
docker compose exec ollama ollama pull qwen3:4b
```

## Writing lessons

Lessons live in `api/content/<course>/*.yaml`, one file per unit. Copy an existing lesson,
change it, and run `pytest`: the content tests check that every exercise loads and accepts its
own answer. Quote any list item that contains a comma or a question mark.

## Adding a module

1. Create `api/app/modules/<name>/router.py` with an `APIRouter(prefix="/api/<name>")`.
2. Include it in `api/app/main.py` and import its models in `app/db.py:init_db`.
3. Flip its entry in `api/app/modules/__init__.py` to `status="ready"`.
4. Add `web/src/routes/<path>/+page.svelte`.
