"""Monte-Carlo equity bot — first non-trivial baseline.

For each decision: estimate win probability vs uniformly-random opponent hands
by simulating to showdown N times, then size the action by pot odds:

  - fold if equity < pot_odds + margin
  - raise pot   if equity > 0.75
  - raise half  if equity > 0.60
  - open-raise  preflop with equity > 0.50 if no one has raised yet
  - else check/call

This isn't strong poker — it ignores fold equity, position, and opponent ranges
— but it's mathematically grounded and should handily beat all three dummies.
"""
from __future__ import annotations

import random

from pokerkit import Card, StandardHighHand

from backend.bots.base import Observation
from backend.events import Action


_DECK_STR = "".join(r + s for r in "23456789TJQKA" for s in "shdc")
_DECK_BY_STR: dict[str, Card] = {
    f"{c.rank}{c.suit}": c for c in Card.parse(_DECK_STR)
}


class EquityBot:
    name = "Equity"

    def __init__(self, n_simulations: int = 120, seed: int | None = None):
        self._n_sims = n_simulations
        self._rng = random.Random(seed)

    def act(self, obs: Observation) -> Action:
        equity = self._estimate_equity(obs)
        return self._choose_action(obs, equity)

    def _estimate_equity(self, obs: Observation) -> float:
        n_opps = sum(
            1 for i, f in enumerate(obs.folded) if not f and i != obs.seat
        )
        if n_opps == 0:
            return 1.0

        hero = [_DECK_BY_STR[c] for c in obs.hole_cards]
        known_board = [_DECK_BY_STR[c] for c in obs.board]
        used = set(obs.hole_cards) | set(obs.board)
        deck = [c for s, c in _DECK_BY_STR.items() if s not in used]

        n_board_to_come = 5 - len(known_board)
        n_opp_cards = 2 * n_opps
        needed = n_opp_cards + n_board_to_come

        wins = 0.0
        for _ in range(self._n_sims):
            self._rng.shuffle(deck)
            sample = deck[:needed]
            opp_hole_chunks = [sample[i : i + 2] for i in range(0, n_opp_cards, 2)]
            full_board = known_board + sample[n_opp_cards:needed]

            hero_eval = StandardHighHand.from_game(hero, full_board)
            best_opp = max(
                StandardHighHand.from_game(h, full_board) for h in opp_hole_chunks
            )

            if hero_eval > best_opp:
                wins += 1.0
            elif not (hero_eval < best_opp):
                # tie — split the pot
                wins += 0.5

        return wins / self._n_sims

    def _choose_action(self, obs: Observation, equity: float) -> Action:
        pot_total = obs.pot + sum(obs.bets)
        pot_odds = obs.to_call / (pot_total + obs.to_call) if obs.to_call > 0 else 0.0
        margin = 0.03

        # Fold against bets we don't have the equity for.
        if obs.to_call > 0 and equity < pot_odds + margin:
            return Action(kind="fold")

        if obs.can_raise:
            target: int | None = None
            if equity > 0.75:
                target = pot_total + obs.to_call               # pot-sized
            elif equity > 0.60:
                target = pot_total // 2 + obs.to_call          # half pot
            elif equity > 0.50 and obs.street == 0 and obs.to_call <= 2 * obs.blinds[1]:
                target = 3 * obs.blinds[1]                     # open-raise

            if target is not None:
                target = max(obs.min_raise, min(obs.max_raise, target))
                return Action(kind="raise_to", amount=target)

        return Action(kind="check_call")
