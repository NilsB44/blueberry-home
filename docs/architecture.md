# Architecture

```
Browser / installed PWA
        │ HTTPS (Caddy local CA)
        ▼
Caddy  ── /api/*  ──►  FastAPI (uvicorn)  ──►  SQLite (WAL) in ./data/api
   │                         │
   └── static SPA            └──►  Ollama (optional, same Docker network or another machine)
```

## Decisions

| Decision | Why |
|---|---|
| One API, many modules | One login, one backup, one deploy. Modules are folders, not services. |
| SQLite in WAL mode | A household's load is tiny; zero ops; the whole DB is one file to back up. |
| Cookie sessions, not JWT | Same-origin SPA behind one proxy; sessions can be revoked by deleting a row. |
| Session tokens stored as SHA-256 | A copied database can't be used to log in. |
| Static SPA served by Caddy | No Node process on the Pi; the browser does the rendering. |
| API proxies Ollama | The model is only reachable by logged-in users; Ollama never leaves the Docker network. |
| `HUB_OLLAMA_URL` configurable | The model can run on a stronger machine without code changes. |
| Rust for poker maths (planned) | Monte Carlo equity is CPU-bound; Rust gets it under a second on the Pi. |

## Conventions

- API routes live under `/api/<module>`; everything else is the SPA.
- Every module has tests in `api/tests/test_<module>.py`.
- Settings come from `HUB_*` environment variables (`api/app/config.py`).
- Schema is created with `create_all` for now; switch to Alembic migrations once real data exists
  (before Phase 1 ships).
