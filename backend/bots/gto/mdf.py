"""Minimum Defense Frequency math.

If opponent bets B into pot P, they're risking B to win P+B. For their bluffs
to break even, you must fold at most B/(B+P+B) of the time. So your *defend*
frequency ≥ P/(P+B).

On the betting side, the symmetric constraint: your value:bluff ratio in your
betting range must be at least (P+B)/B for opponents to be priced into being
indifferent. (Pot-sized bet → 2:1 value:bluff.)
"""
from __future__ import annotations


def required_defense_freq(bet: int, pot_before_bet: int) -> float:
    """Minimum fraction of your range you must continue with vs a bet of `bet` into `pot_before_bet`."""
    if bet <= 0:
        return 1.0
    return pot_before_bet / (pot_before_bet + bet)


def required_value_to_bluff(bet: int, pot_before_bet: int) -> float:
    """As the bettor: minimum value:bluff ratio in your betting range.
    Returns the multiplier — e.g. 2.0 for a pot-sized bet (2 value combos per bluff combo)."""
    if bet <= 0:
        return float("inf")
    return (pot_before_bet + bet) / bet


def bluff_share_for_size(bet: int, pot_before_bet: int) -> float:
    """As the bettor: what fraction of your *betting range* should be bluffs.
    1/3 for pot, 2/5 for half-pot, etc. (= bet / (pot + 2*bet))."""
    if bet <= 0:
        return 0.0
    return bet / (pot_before_bet + 2 * bet)
