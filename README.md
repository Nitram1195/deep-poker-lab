# Deep Poker Lab

A bots-only NLHE table you can watch in the browser. Backend is FastAPI +
WebSocket, frontend is SvelteKit.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (Python ≥ 3.12, managed by uv)
- Node.js (for the frontend)

## Install

```bash
uv sync                    # backend deps into .venv/
cd frontend && npm install # frontend deps
```

## Run

Two terminals.

**Backend** (from repo root):

```bash
uv run uvicorn backend.main:app --reload
```

Serves on http://127.0.0.1:8000 — `/health` for a ping, `/ws` for the table feed.

**Frontend** (from `frontend/`):

```bash
npm run dev
```

Opens on http://127.0.0.1:5173.

## Optional: enable the LLM bot

The LLM seat is skipped unless `GROQ_API_KEY` is set:

```bash
GROQ_API_KEY=sk-... uv run uvicorn backend.main:app --reload
# optionally override the model (default: llama-3.3-70b-versatile)
GROQ_MODEL=llama-3.3-70b-versatile GROQ_API_KEY=... uv run uvicorn backend.main:app --reload
```

## Benchmark mode

Play the bots head-to-head with no UI delays and print final stats (hands,
net chips, bb/100, VPIP, PFR). No frontend needed.

```bash
uv run python -m backend.benchmark --hands 500
```

Flags:

- `--hands N` — number of hands (default `10000`)
- `--include-llm` — include the Groq LLM bot (needs `GROQ_API_KEY`)

Progress is printed every 100 hands. Press **Ctrl+C** to stop early — the
current hand finishes and the final table is printed normally. Press Ctrl+C
twice to force-quit.

> The default `EquityBot` runs 120 Monte Carlo simulations per decision, which
> dominates runtime (~2 hands/s). Lower `n_simulations` in
> `backend/benchmark.py` for faster smoke runs.

## Tests

```bash
uv run pytest
```