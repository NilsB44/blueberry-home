# The Claude page

An owner-only page (dashboard tile **Claude**) showing how much Claude is being used.

## What it can and can't show

| | Shown | Where it comes from |
|---|---|---|
| Your Claude plan's remaining allowance and reset time | **No**, link only | Only claude.ai shows this (Settings → Usage). Anthropic has no API for it. |
| Claude Code on the Pi: tokens per day, 7- and 30-day averages, per model, per project folder, sessions, cache hit rate | Yes | Claude Code's own session logs |
| What that use would cost at API prices, per day and per month at the current pace | Yes | The logs × Anthropic's published prices (`api/app/modules/claude/pricing.py`) |
| Spend on Anthropic API keys, per day and per model | Optional | The Usage and Cost Admin API |

"At API prices" isn't what you pay on a plan; it's a consistent way to compare days and
see what's expensive (cache reads are a tenth of the price, so a high cache rate is good).

## Turning it on

Claude Code writes a log per session under `~/.claude/projects` on the machine where it runs.
Once it runs on the Pi, add to `.env`:

```
HUB_CLAUDE_LOGS=/home/<you>/.claude/projects
```

and restart with `docker compose up -d`. The folder is mounted read-only; the hub never
changes it. The API container runs as user 1000, which is the first user on Raspberry Pi OS,
so it can read your logs.

### API keys (optional)

Only for organisation accounts on console.anthropic.com (the Admin API isn't available to
individual accounts). Create an Admin API key (`sk-ant-admin...`) and add it:

```
HUB_ANTHROPIC_ADMIN_KEY=sk-ant-admin01-...
```

The key only ever goes to `api.anthropic.com`, is never sent to the browser, and results are
cached for 10 minutes.

## Updating prices

New models or price changes: edit `PRICES` in `api/app/modules/claude/pricing.py`. A model
that isn't listed shows "–" instead of a cost.
