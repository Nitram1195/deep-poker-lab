"""Per-opponent range tracking.

A range is a weighted set of starting-hand combos (tuple of two card strings).
The model starts wide and narrows after each action observed:

  preflop raise   -> top ~15% of remaining range
  preflop call    -> ~40% (call-range; speculative + medium)
  preflop limp    -> ~60% (very wide, weak ranges)
  flop bet        -> top ~50% of remaining (made hands + draws + bluffs)
  flop check      -> bottom ~70% (checking range — mostly weak/mediums)

These percentiles are deliberate simplifications. The point is: every action
moves the range; equity calculations consume the *current* range, not a
random hand.
"""
from __future__ import annotations

import random

from backend.bots.gto.preflop_charts import RANK_VALUE, hand_class

_DECK = [r + s for r in "23456789TJQKA" for s in "shdc"]


def all_combos() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for i in range(52):
        for j in range(i + 1, 52):
            out.append((_DECK[i], _DECK[j]))
    return out


# Approximate preflop equity vs random hand, in win-rate %, by hand class.
# Higher = stronger preflop. Hand-curated from common Sklansky-style charts;
# values needn't be exact — only the ordering matters for narrowing.
_HAND_CLASS_EQUITY: dict[str, float] = {
    # pairs
    "AA": 85.0, "KK": 82.0, "QQ": 80.0, "JJ": 77.0, "TT": 75.0,
    "99": 71.5, "88": 69.0, "77": 66.5, "66": 63.5, "55": 60.0,
    "44": 57.0, "33": 53.5, "22": 50.5,
    # suited aces
    "AKs": 67.0, "AQs": 66.0, "AJs": 65.5, "ATs": 64.5, "A9s": 62.5,
    "A8s": 61.5, "A7s": 60.5, "A6s": 59.0, "A5s": 59.0, "A4s": 58.5,
    "A3s": 57.5, "A2s": 56.5,
    # offsuit aces
    "AKo": 65.0, "AQo": 64.0, "AJo": 63.0, "ATo": 62.0, "A9o": 60.0,
    "A8o": 58.5, "A7o": 57.5, "A6o": 56.0, "A5o": 56.0, "A4o": 55.5,
    "A3o": 54.5, "A2o": 53.5,
    # suited kings
    "KQs": 63.5, "KJs": 62.5, "KTs": 61.5, "K9s": 59.5, "K8s": 58.0,
    "K7s": 57.0, "K6s": 56.0, "K5s": 55.0, "K4s": 54.0, "K3s": 53.5,
    "K2s": 52.5,
    "KQo": 61.5, "KJo": 60.5, "KTo": 59.0, "K9o": 56.5, "K8o": 54.5,
    "K7o": 53.5, "K6o": 52.5, "K5o": 51.5, "K4o": 50.5, "K3o": 50.0,
    "K2o": 49.5,
    # queens
    "QJs": 60.5, "QTs": 59.5, "Q9s": 58.0, "Q8s": 56.0, "Q7s": 54.5,
    "Q6s": 53.5, "Q5s": 52.5, "Q4s": 51.5, "Q3s": 50.5, "Q2s": 50.0,
    "QJo": 58.0, "QTo": 57.0, "Q9o": 55.0, "Q8o": 52.5, "Q7o": 50.5,
    "Q6o": 49.5, "Q5o": 48.5, "Q4o": 47.5, "Q3o": 46.5, "Q2o": 45.5,
    # jacks
    "JTs": 58.0, "J9s": 56.5, "J8s": 54.5, "J7s": 52.5, "J6s": 50.5,
    "J5s": 49.5, "J4s": 48.5, "J3s": 47.5, "J2s": 46.5,
    "JTo": 55.5, "J9o": 53.5, "J8o": 51.0, "J7o": 49.0, "J6o": 46.5,
    "J5o": 45.5, "J4o": 44.5, "J3o": 43.5, "J2o": 42.5,
    # tens
    "T9s": 55.5, "T8s": 53.5, "T7s": 51.5, "T6s": 49.5, "T5s": 47.5,
    "T4s": 46.5, "T3s": 45.5, "T2s": 44.5,
    "T9o": 52.5, "T8o": 50.0, "T7o": 47.5, "T6o": 45.0, "T5o": 43.0,
    "T4o": 41.5, "T3o": 40.5, "T2o": 39.5,
    # nines and below — suited
    "98s": 53.0, "97s": 51.0, "96s": 49.0, "95s": 47.0, "94s": 44.5,
    "93s": 43.0, "92s": 41.5,
    "98o": 49.5, "97o": 47.0, "96o": 45.0, "95o": 42.5,
    "87s": 51.0, "86s": 49.0, "85s": 47.0, "84s": 44.5,
    "87o": 47.5, "86o": 45.0, "85o": 42.5,
    "76s": 49.5, "75s": 47.5, "74s": 45.0,
    "76o": 46.0, "75o": 43.5,
    "65s": 48.0, "64s": 46.0, "63s": 43.0,
    "65o": 44.5, "64o": 42.0,
    "54s": 46.5, "53s": 44.5,
    "54o": 43.0, "53o": 40.5,
    "43s": 44.5, "42s": 42.0,
    "32s": 42.5,
}


def hand_class_equity(hand: str) -> float:
    return _HAND_CLASS_EQUITY.get(hand, 35.0)  # default: trash


class OpponentRange:
    """Weighted set of opponent's possible hand combos."""

    def __init__(self, dead_cards: set[str] | None = None):
        dead = dead_cards or set()
        self.weights: dict[tuple[str, str], float] = {}
        for combo in all_combos():
            if combo[0] in dead or combo[1] in dead:
                continue
            self.weights[combo] = 1.0

    def __len__(self) -> int:
        return sum(1 for w in self.weights.values() if w > 0)

    def remove_dead(self, dead_cards: set[str]) -> None:
        self.weights = {
            c: w for c, w in self.weights.items()
            if c[0] not in dead_cards and c[1] not in dead_cards
        }

    def narrow_to_top(self, fraction: float) -> None:
        """Keep only the top `fraction` of combos by class-equity."""
        if fraction >= 1.0 or not self.weights:
            return
        items = list(self.weights.items())
        items.sort(key=lambda kv: -hand_class_equity(hand_class(kv[0][0], kv[0][1])))
        n_keep = max(1, int(len(items) * fraction))
        self.weights = {c: w for c, w in items[:n_keep]}

    def narrow_to_bottom(self, fraction: float) -> None:
        """Keep only the bottom `fraction` of combos by class-equity (e.g., a check range)."""
        if fraction >= 1.0 or not self.weights:
            return
        items = list(self.weights.items())
        items.sort(key=lambda kv: hand_class_equity(hand_class(kv[0][0], kv[0][1])))
        n_keep = max(1, int(len(items) * fraction))
        self.weights = {c: w for c, w in items[:n_keep]}

    def sample(self, rng: random.Random) -> tuple[str, str] | None:
        """Sample one combo, weighted. Returns None if range is empty."""
        if not self.weights:
            return None
        total = sum(self.weights.values())
        if total <= 0:
            return None
        r = rng.random() * total
        cum = 0.0
        for combo, w in self.weights.items():
            cum += w
            if r <= cum:
                return combo
        # Fallback for floating-point edge cases.
        return next(iter(self.weights))


# Action -> tightness fraction. Used to apply a default narrowing.
PREFLOP_NARROW_BY_ACTION = {
    "raise_to": 0.15,    # raised → premium-ish range
    "check_call": 0.40,  # called a raise → speculative + medium
    "fold": 0.0,         # not relevant; opponent is out
}

POSTFLOP_NARROW_BY_ACTION = {
    "raise_to": 0.40,    # bet → made hands + draws + some bluffs
    "check_call": 0.55,  # call → bluff-catchers + draws
    "fold": 0.0,
}
