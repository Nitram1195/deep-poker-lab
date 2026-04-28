"""FastAPI app entrypoint. Spawns the GameRunner on startup, exposes /ws."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.bots.always_call import AlwaysCallBot
from backend.bots.always_fold import AlwaysFoldBot
from backend.bots.base import Bot
from backend.bots.equity import EquityBot
from backend.bots.llm import LLMBot
from backend.bots.random_bot import RandomBot
from backend.bots.tight_aggro import TightAggroRuleBot
from backend.events import Snapshot
from backend.runner import GameRunner
from backend.ws import ConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("backend")


def _build_runner(broadcast) -> GameRunner:
    bots: list[Bot] = [
        RandomBot(seed=42),
        AlwaysCallBot(),
        AlwaysFoldBot(),
        TightAggroRuleBot(),
        EquityBot(n_simulations=120, seed=7),
    ]

    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        # llama-3.3-70b-versatile is a non-reasoning model and more reliable for
        # structured-JSON output than the reasoning gpt-oss models on Groq's free tier.
        groq_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        bots.append(
            LLMBot(
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_key,
                model=groq_model,
                name=f"groq:{groq_model.split('/')[-1]}",
            )
        )
        log.info("LLM bot enabled (groq, model=%s)", groq_model)
    else:
        log.info("GROQ_API_KEY not set — LLM bot disabled")

    return GameRunner(bots=bots, broadcast=broadcast, starting_stack=200, blinds=(1, 2))


@asynccontextmanager
async def lifespan(app: FastAPI):
    cm = ConnectionManager()
    runner = _build_runner(cm.broadcast)
    app.state.cm = cm
    app.state.runner = runner
    runner.start()
    log.info("game runner started")
    try:
        yield
    finally:
        log.info("shutting down")
        await runner.stop()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # dev only
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"ok": True}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    cm: ConnectionManager = ws.app.state.cm
    runner: GameRunner = ws.app.state.runner
    await cm.connect(ws)
    try:
        snapshot = Snapshot(
            bots=[b.name for b in runner._bots],
            leaderboard=runner.leaderboard(),
            in_hand=runner.in_hand,
            current_hand_id=runner._hand_id or None,
            sitting_out=runner.sitting_out,
        )
        await cm.send(ws, snapshot)
        while True:
            data = await ws.receive_json()
            cmd = data.get("cmd") if isinstance(data, dict) else None
            seat = data.get("seat") if isinstance(data, dict) else None
            if cmd in ("sit_out", "sit_in") and isinstance(seat, int):
                await runner.set_sitting_out(seat, cmd == "sit_out")
            else:
                log.warning("ws: ignoring unknown command %r", data)
    except WebSocketDisconnect:
        pass
    finally:
        await cm.disconnect(ws)
