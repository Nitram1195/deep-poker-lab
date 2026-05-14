"""Benchmark mode: play bots head-to-head as fast as possible, print final stats.

Usage:
    uv run python -m backend.benchmark --hands 10000
    uv run python -m backend.benchmark --hands 5000 --include-llm
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import time
import warnings

from backend.bots.base import Bot
from backend.bots.equity import EquityBot
from backend.bots.gto import GTOBot
from backend.bots.llm import LLMBot
from backend.bots.random_bot import RandomBot
from backend.bots.tight_aggro import TightAggroRuleBot
from backend.runner import GameRunner


def _build_bots(include_llm: bool) -> list[Bot]:
    bots: list[Bot] = [
        RandomBot(seed=42),
        TightAggroRuleBot(),
        EquityBot(n_simulations=120, seed=7),
        GTOBot(seed=11),
    ]
    if include_llm:
        groq_key = os.environ.get("GROQ_API_KEY")
        if not groq_key:
            raise SystemExit("--include-llm requires GROQ_API_KEY in the environment")
        groq_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        bots.append(
            LLMBot(
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_key,
                model=groq_model,
                name=f"groq:{groq_model.split('/')[-1]}",
            )
        )
    return bots


async def _noop_broadcast(_event) -> None:
    return None


# Flipped by the SIGINT handler. The per-hand loop checks it between hands so
# Ctrl-C finishes the current hand and then prints the table normally.
_stop_requested = False


def _install_sigint_handler() -> None:
    def _handler(_sig, _frame):
        global _stop_requested
        if _stop_requested:
            # Second Ctrl-C → escalate to a real interrupt.
            raise KeyboardInterrupt
        _stop_requested = True
        print(
            "\n^C — finishing current hand, then printing results "
            "(Ctrl-C again to force-quit).",
            file=sys.stderr,
            flush=True,
        )

    signal.signal(signal.SIGINT, _handler)


def _print_table(runner: GameRunner, n_hands: int, elapsed: float, big_blind: int) -> None:
    rows = sorted(runner.leaderboard(), key=lambda e: -e.net_chips)
    name_w = max(len("Bot"), *(len(r.bot_name) for r in rows))
    rate = n_hands / elapsed if elapsed > 0 else 0.0

    print(f"\nBenchmark: {n_hands} hands in {elapsed:.2f}s ({rate:,.0f} hands/s)\n")
    header = f"{'Bot':<{name_w}}  {'Hands':>7}  {'Net':>8}  {'bb/100':>8}  {'VPIP':>5}  {'PFR':>5}"
    print(header)
    print("-" * len(header))
    for r in rows:
        bb_per_100 = (r.net_chips / big_blind / r.hands_played * 100) if r.hands_played else 0.0
        vpip = f"{r.vpip / r.hands_played * 100:.0f}%" if r.hands_played else "—"
        pfr = f"{r.pfr / r.hands_played * 100:.0f}%" if r.hands_played else "—"
        sign = "+" if r.net_chips > 0 else ""
        print(
            f"{r.bot_name:<{name_w}}  {r.hands_played:>7}  {sign + str(r.net_chips):>8}  "
            f"{bb_per_100:>+8.2f}  {vpip:>5}  {pfr:>5}"
        )
    print()


async def _run(n_hands: int, include_llm: bool) -> None:
    bots = _build_bots(include_llm)
    blinds = (1, 2)
    runner = GameRunner(
        bots=bots,
        broadcast=_noop_broadcast,
        starting_stack=200,
        blinds=blinds,
        delay_scale=0.0,
    )
    start = time.perf_counter()
    played = 0
    progress_every = 100
    # Per-hand loop instead of runner.play_hands so we can check the SIGINT flag
    # and log progress between hands.
    for i in range(1, n_hands + 1):
        if _stop_requested:
            break
        await runner._play_one_hand()
        played = i
        if i % progress_every == 0:
            elapsed = time.perf_counter() - start
            rate = i / elapsed if elapsed > 0 else 0.0
            eta = (n_hands - i) / rate if rate > 0 else 0.0
            print(
                f"  ... {i}/{n_hands} hands  ({rate:.1f} h/s, ETA {eta:.0f}s)",
                file=sys.stderr,
                flush=True,
            )
    elapsed = time.perf_counter() - start
    _print_table(runner, played, elapsed, big_blind=blinds[1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bots head-to-head with no delays.")
    parser.add_argument("--hands", type=int, default=10_000, help="hands to play (default: 10000)")
    parser.add_argument("--include-llm", action="store_true", help="include the LLM bot (needs GROQ_API_KEY)")
    args = parser.parse_args()

    # Quiet the noisy bits: pokerkit's "no reason to fold" warning, INFO logs.
    warnings.filterwarnings("ignore", category=UserWarning, module="pokerkit")
    logging.basicConfig(level=logging.WARNING)

    _install_sigint_handler()
    asyncio.run(_run(args.hands, args.include_llm))


if __name__ == "__main__":
    main()
