"""API list prices per million tokens, to put a dollar figure on Claude Code use.

On a Claude plan you don't pay these: they show what the same use would cost on the API,
which is a fair way to compare days. Cache reads cost a tenth of input; writing to the cache
costs 1.25x input (5-minute cache) or 2x (1-hour cache)."""

# (model id prefix, input $/M, output $/M). Longest prefix wins, so "claude-opus-5-5" isn't
# priced as "claude-opus-5".
PRICES: list[tuple[str, float, float]] = [
    ("claude-fable-5-1", 10.0, 50.0),
    ("claude-fable-5", 10.0, 50.0),
    ("claude-mythos-5", 10.0, 50.0),
    ("claude-opus-5-5", 4.0, 20.0),
    ("claude-opus-5", 5.0, 25.0),
    ("claude-opus-4", 5.0, 25.0),
    ("claude-sonnet-5-5", 2.0, 10.0),
    ("claude-sonnet-5", 2.0, 10.0),
    ("claude-sonnet-4", 3.0, 15.0),
    ("claude-haiku-5-5", 0.10, 0.50),
    ("claude-haiku-4", 1.0, 5.0),
]


def price(model: str) -> tuple[float, float] | None:
    model = model.split("[")[0].lower()
    matches = [p for p in PRICES if model.startswith(p[0])]
    if not matches:
        return None
    _, inp, out = max(matches, key=lambda p: len(p[0]))
    return inp, out


def cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read: int,
    cache_write_5m: int,
    cache_write_1h: int,
) -> float | None:
    p = price(model)
    if p is None:
        return None
    inp, out = p
    return (
        input_tokens * inp
        + output_tokens * out
        + cache_read * inp * 0.1
        + cache_write_5m * inp * 1.25
        + cache_write_1h * inp * 2
    ) / 1_000_000
