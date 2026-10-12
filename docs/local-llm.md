# Local language model

## Can a Pi 5 (8 GB) run one?

Yes, small ones. The Pi has no GPU that Ollama can use, so models run on the 4 CPU cores.
Rough expectations for 4-bit quantised models (inferred from typical Pi 5 benchmarks; measure
on your own board):

| Model size | RAM used | Speed on Pi 5 | Good for |
|---|---|---|---|
| ~1–2B (e.g. `qwen3:1.7b`, `gemma3:1b`) | 1.5–2.5 GB | ~8–15 tokens/s | Quick answers, classifying, short summaries |
| ~3–4B (e.g. `qwen3:4b`, default) | 3–4 GB | ~3–6 tokens/s | Explaining French grammar, example sentences, simple tool calls |
| 7–8B | 5–6 GB | ~1–2 tokens/s | Usable only for patient, background jobs; squeezes everything else |

The first reply after the model loads takes extra seconds. `OLLAMA_KEEP_ALIVE=10m` unloads it
when idle so the rest of the hub gets its RAM back.

## Agent features worth building

An "agent" here means the model can call the hub's own API as tools. Small models handle a few
well-defined tools reliably; they struggle with long multi-step plans. Good fits:

- **French tutor:** "why is this wrong?" explanations on lesson mistakes; generate extra example
  sentences for a word; role-play a café order at A1 level.
- **Hub helper:** "what's due for review today?", "log 300 ml water for the monstera",
  "what did I win at poker this month?" — the model picks a tool, the API does the real work.
- **Summaries:** summarise a YouTube transcript or a book chapter into flashcards.
- **Poker:** explain an equity result in plain words. Never let the model do the maths itself;
  the Rust engine computes, the model narrates.

## Running the model on a stronger computer instead

If you have a desktop or laptop with a GPU (or an Apple Silicon Mac), run Ollama there and point
the hub at it in `.env`:

```
HUB_OLLAMA_URL=http://192.168.1.50:11434
```

On that machine, start Ollama with `OLLAMA_HOST=0.0.0.0` so the Pi can reach it, and firewall
port 11434 to the Pi's IP only. 7–14B models then become fast, and the Pi stays light. The hub's
assistant page works the same either way; when the computer is off, it shows the model as offline.
