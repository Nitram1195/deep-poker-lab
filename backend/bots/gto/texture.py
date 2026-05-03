"""Board texture classification for sizing decisions.

Outputs are simple labels and a `wetness` score 0..3 used by the bot to pick
bet sizes (drier boards take smaller bets, wetter boards bigger).
"""
from __future__ import annotations

from dataclasses import dataclass

_RANK_ORDER = "23456789TJQKA"
_RANK_VALUE = {r: i for i, r in enumerate(_RANK_ORDER)}


@dataclass
class Texture:
    paired: bool        # at least two ranks match on board
    monotone: bool      # all same suit
    two_tone: bool      # exactly two suits
    connected: bool     # straight-friendly
    high_card: int      # value of highest rank on board (0..12)
    wetness: int        # 0=dry, 3=very wet


def texture(board: list[str]) -> Texture:
    if len(board) < 3:
        return Texture(False, False, False, False, 0, 0)
    suits = [c[1] for c in board]
    ranks = sorted({_RANK_VALUE[c[0]] for c in board})
    rank_list = [_RANK_VALUE[c[0]] for c in board]

    paired = len(set(rank_list)) < len(rank_list)
    suit_count = len(set(suits))
    monotone = suit_count == 1
    two_tone = suit_count == 2
    # Connected = at least two cards within 4 ranks of each other (straight draws live)
    connected = (max(ranks) - min(ranks)) <= 4 and len(ranks) >= 2

    wet_score = 0
    if monotone:
        wet_score += 2
    elif two_tone:
        wet_score += 1
    if connected and not paired:
        wet_score += 1
    wet_score = min(3, wet_score)

    high_card = max(rank_list)
    return Texture(paired, monotone, two_tone, connected, high_card, wet_score)
