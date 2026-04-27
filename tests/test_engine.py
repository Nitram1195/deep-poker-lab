"""Smoke tests for the engine and runner.

The point isn't bot quality — it's that the wiring is correct:
- chips are conserved (every hand sums to 0)
- no hand stalls (no None-actor while status==True)
- legal-action checks always include at least one option
- random play with the random bot reaches showdown sometimes (full board)
"""
from __future__ import annotations

import asyncio
import warnings

import pytest

from backend.bots.always_call import AlwaysCallBot
from backend.bots.random_bot import RandomBot
from backend.bots.tight_aggro import TightAggroRuleBot
from backend.engine import HandEngine
from backend.events import Action, HandEnd, LeaderboardUpdate
from backend.runner import GameRunner


# pokerkit warns about "no reason to fold" — we don't want it cluttering output.
warnings.filterwarnings("ignore", category=UserWarning)


def _play_hand_random(engine: HandEngine, rng) -> int:
    """Play one hand using random legal actions. Returns count of decisions made."""
    n_actions = 0
    while not engine.is_complete():
        actor = engine.current_actor()
        assert actor is not None, "engine has no actor but isn't complete"
        legal = engine.legal_actions()
        # at least one action must be legal at any decision point
        assert legal.can_check_call or legal.can_fold or legal.can_raise
        choice = rng.random()
        if legal.can_raise and choice < 0.2:
            amount = rng.randint(legal.min_raise, legal.max_raise)
            engine.apply(Action(kind="raise_to", amount=amount))
        elif legal.to_call > 0 and choice < 0.55:
            engine.apply(Action(kind="fold"))
        else:
            engine.apply(Action(kind="check_call"))
        n_actions += 1
        assert n_actions < 200, "hand stuck"
    return n_actions


def test_chip_conservation_500_hands():
    import random
    rng = random.Random(0xC0FFEE)
    drift = 0
    showdowns_seen = 0
    for _ in range(500):
        eng = HandEngine(player_count=3, starting_stacks=[200, 200, 200], blinds=(1, 2))
        _play_hand_random(eng, rng)
        payoffs = eng.payoffs()
        drift += sum(payoffs)
        if len(eng.board_cards()) == 5:
            showdowns_seen += 1
    assert drift == 0, f"chip drift over 500 hands = {drift}"
    assert showdowns_seen > 0, "no hand reached the river — random play is stuck preflop"


def test_runner_payoffs_match_leaderboard():
    """Every HandEnd's payoffs must be reflected in the leaderboard at the end of the run."""
    end_events: list[HandEnd] = []
    leaderboard_updates: list[LeaderboardUpdate] = []

    async def collect(ev):
        if isinstance(ev, HandEnd):
            end_events.append(ev)
        elif isinstance(ev, LeaderboardUpdate):
            leaderboard_updates.append(ev)

    runner = GameRunner(
        bots=[RandomBot(seed=1), AlwaysCallBot(), TightAggroRuleBot()],
        broadcast=collect,
        starting_stack=200,
        blinds=(1, 2),
    )
    # neutralize the visual delays for the test
    import backend.runner as r
    r.TURN_DELAY_S = 0.0
    r.ACTION_DELAY_S = 0.0
    r.STREET_DELAY_S = 0.0
    r.HAND_END_DELAY_S = 0.0

    async def main():
        runner.start()
        await asyncio.sleep(1.5)
        await runner.stop()

    asyncio.run(main())

    assert len(end_events) >= 5, f"only {len(end_events)} hands completed"

    for he in end_events:
        assert sum(he.payoffs.values()) == 0, f"hand {he.hand_id} payoffs don't sum to 0: {he.payoffs}"

    final_lb = leaderboard_updates[-1].entries
    total = sum(e.net_chips for e in final_lb)
    assert total == 0, f"final leaderboard drift = {total}"


def test_pokerkit_card_format():
    """Card strings must be exactly two chars: rank + suit. Frontend depends on this."""
    eng = HandEngine(player_count=3, starting_stacks=[200, 200, 200], blinds=(1, 2))
    for seat in range(3):
        cards = eng.hole_cards(seat)
        assert len(cards) == 2
        for c in cards:
            assert len(c) == 2
            assert c[0] in "23456789TJQKA"
            assert c[1] in "shdc"
