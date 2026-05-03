"""Preflop strategy tables.

Each chart maps a 169-class hand id (e.g. "AKs") to a probability distribution
over abstract actions: ``open``, ``call``, ``three_bet``, ``four_bet``, ``fold``.

Hands not in a chart default to "fold" (or "check" if no one has bet).

These are hand-tuned approximations of 6-max GTO ranges — they're intentionally
simpler than what a real solver would output. The graduation path is to replace
these tables with CFR-trained outputs without touching the bot logic.
"""
from __future__ import annotations

RANK_ORDER = "23456789TJQKA"
RANK_VALUE = {r: i for i, r in enumerate(RANK_ORDER)}


def hand_class(c1: str, c2: str) -> str:
    """Canonical hand class id. ('Ah','Kd') -> 'AKo'; ('Ah','Kh') -> 'AKs'; ('Ah','Ad') -> 'AA'."""
    r1, r2 = c1[0], c2[0]
    s1, s2 = c1[1], c2[1]
    if r1 == r2:
        return r1 + r2
    if RANK_VALUE[r1] < RANK_VALUE[r2]:
        r1, r2 = r2, r1
    return r1 + r2 + ("s" if s1 == s2 else "o")


# Position labels for 6-max. Engine seats 0/1 are SB/BB; the rest are
# distance-from-button: 0=BTN, 1=CO, 2=MP/HJ, 3=UTG.
def position_label(seat: int, button_seat: int, n_active: int) -> str:
    if n_active == 2:
        return "BTN" if seat == button_seat else "BB"
    if seat == 0:
        return "SB"
    if seat == 1:
        return "BB"
    distance = button_seat - seat
    if distance <= 0:
        return "BTN"
    if distance == 1:
        return "CO"
    if distance == 2:
        return "MP"
    return "UTG"


# ---- Open-raising ranges (no one has raised yet) ----
# Tighter from UTG, much wider from BTN.
UTG_OPEN: dict[str, list[tuple[str, float]]] = {
    h: [("open", 1.0)] for h in [
        "AA", "KK", "QQ", "JJ", "TT", "99",
        "AKs", "AKo", "AQs", "AQo", "AJs",
        "KQs",
    ]
} | {
    "88": [("open", 0.7), ("fold", 0.3)],
    "77": [("open", 0.5), ("fold", 0.5)],
    "AJo": [("open", 0.6), ("fold", 0.4)],
    "ATs": [("open", 0.8), ("fold", 0.2)],
    "KJs": [("open", 0.6), ("fold", 0.4)],
    "KTs": [("open", 0.4), ("fold", 0.6)],
    "QJs": [("open", 0.5), ("fold", 0.5)],
    "JTs": [("open", 0.5), ("fold", 0.5)],
}

MP_OPEN: dict[str, list[tuple[str, float]]] = {
    **UTG_OPEN,
    **{h: [("open", 1.0)] for h in [
        "88", "77", "66",
        "AJo", "ATs", "ATo",
        "KJs", "KTs", "KQo",
        "QJs", "JTs",
    ]},
    "55": [("open", 0.6), ("fold", 0.4)],
    "44": [("open", 0.4), ("fold", 0.6)],
    "T9s": [("open", 0.7), ("fold", 0.3)],
    "98s": [("open", 0.5), ("fold", 0.5)],
    "QTs": [("open", 0.7), ("fold", 0.3)],
    "KJo": [("open", 0.5), ("fold", 0.5)],
}

CO_OPEN: dict[str, list[tuple[str, float]]] = {
    **MP_OPEN,
    **{h: [("open", 1.0)] for h in [
        "55", "44", "33", "22",
        "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "K9s", "Q9s", "J9s", "T9s",
        "98s", "87s", "76s", "65s",
        "QTs", "KJo",
    ]},
    "A9o": [("open", 0.6), ("fold", 0.4)],
    "KTo": [("open", 0.5), ("fold", 0.5)],
    "QJo": [("open", 0.5), ("fold", 0.5)],
    "JTo": [("open", 0.4), ("fold", 0.6)],
    "T8s": [("open", 0.7), ("fold", 0.3)],
    "97s": [("open", 0.5), ("fold", 0.5)],
    "86s": [("open", 0.4), ("fold", 0.6)],
    "75s": [("open", 0.3), ("fold", 0.7)],
    "54s": [("open", 0.5), ("fold", 0.5)],
}

BTN_OPEN: dict[str, list[tuple[str, float]]] = {
    **CO_OPEN,
    **{h: [("open", 1.0)] for h in [
        "A9o", "A8o", "A7o", "A6o", "A5o",
        "K9o", "Q9o", "J9o", "T9o", "98o",
        "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
        "Q8s", "J8s", "T8s",
        "97s", "86s", "75s", "54s",
        "KTo", "QJo", "JTo",
    ]},
    "Q7s": [("open", 0.7), ("fold", 0.3)],
    "Q6s": [("open", 0.5), ("fold", 0.5)],
    "J7s": [("open", 0.5), ("fold", 0.5)],
    "T7s": [("open", 0.5), ("fold", 0.5)],
    "96s": [("open", 0.4), ("fold", 0.6)],
    "85s": [("open", 0.3), ("fold", 0.7)],
    "64s": [("open", 0.4), ("fold", 0.6)],
    "53s": [("open", 0.4), ("fold", 0.6)],
    "43s": [("open", 0.3), ("fold", 0.7)],
    "A4o": [("open", 0.5), ("fold", 0.5)],
    "A3o": [("open", 0.4), ("fold", 0.6)],
    "A2o": [("open", 0.3), ("fold", 0.7)],
    "K9o": [("open", 0.7), ("fold", 0.3)],
}

# SB plays roughly cutoff range when folded to (slightly modified for OOP).
SB_OPEN: dict[str, list[tuple[str, float]]] = {**CO_OPEN}

OPEN_BY_POSITION: dict[str, dict[str, list[tuple[str, float]]]] = {
    "UTG": UTG_OPEN,
    "MP": MP_OPEN,
    "CO": CO_OPEN,
    "BTN": BTN_OPEN,
    "SB": SB_OPEN,
    "BB": BTN_OPEN,  # if we get to act-first as BB in a multiway limp, treat as wide
}


# ---- Facing a single raise: 3-bet for value, mix some bluffs, call speculative.
# We don't know the raiser's exact position in v1 — use one chart per OUR position.
VS_RAISE_DEFAULT: dict[str, list[tuple[str, float]]] = {
    # value 3-bets (almost always raise)
    "AA": [("three_bet", 1.0)],
    "KK": [("three_bet", 1.0)],
    "QQ": [("three_bet", 0.85), ("call", 0.15)],
    "AKs": [("three_bet", 0.85), ("call", 0.15)],
    "AKo": [("three_bet", 0.7), ("call", 0.3)],
    # mixed
    "JJ": [("three_bet", 0.5), ("call", 0.5)],
    "TT": [("three_bet", 0.3), ("call", 0.7)],
    "AQs": [("three_bet", 0.4), ("call", 0.6)],
    "AQo": [("three_bet", 0.25), ("call", 0.55), ("fold", 0.2)],
    "AJs": [("three_bet", 0.2), ("call", 0.8)],
    "KQs": [("three_bet", 0.2), ("call", 0.8)],
    # set-mining / speculative calls
    **{h: [("call", 1.0)] for h in [
        "99", "88", "77", "66", "55", "44",
        "AJo", "KQo", "ATs", "KJs", "KTs", "QJs", "QTs", "JTs",
        "T9s", "98s", "87s", "76s",
    ]},
    "33": [("call", 0.7), ("fold", 0.3)],
    "22": [("call", 0.6), ("fold", 0.4)],
    # blocker bluffs (3-bet with hands that block AA/KK/AK)
    "A5s": [("three_bet", 0.4), ("call", 0.4), ("fold", 0.2)],
    "A4s": [("three_bet", 0.4), ("call", 0.3), ("fold", 0.3)],
    "A3s": [("three_bet", 0.3), ("call", 0.3), ("fold", 0.4)],
    "A2s": [("three_bet", 0.2), ("call", 0.3), ("fold", 0.5)],
    "K5s": [("three_bet", 0.15), ("call", 0.2), ("fold", 0.65)],
}


# ---- Facing a 3-bet (we opened, opponent 3-bet): 4-bet very tight, call medium.
VS_THREE_BET_DEFAULT: dict[str, list[tuple[str, float]]] = {
    "AA": [("four_bet", 1.0)],
    "KK": [("four_bet", 1.0)],
    "QQ": [("four_bet", 0.7), ("call", 0.3)],
    "AKs": [("four_bet", 0.6), ("call", 0.4)],
    "AKo": [("four_bet", 0.55), ("call", 0.45)],
    "JJ": [("call", 0.8), ("four_bet", 0.1), ("fold", 0.1)],
    "TT": [("call", 0.7), ("fold", 0.3)],
    "AQs": [("call", 0.7), ("fold", 0.3)],
    "AQo": [("call", 0.4), ("fold", 0.6)],
    "AJs": [("call", 0.5), ("fold", 0.5)],
    "KQs": [("call", 0.5), ("fold", 0.5)],
    # 4-bet bluffs with blockers
    "A5s": [("four_bet", 0.3), ("call", 0.2), ("fold", 0.5)],
    "A4s": [("four_bet", 0.2), ("call", 0.2), ("fold", 0.6)],
    # set-mining when prices are right
    **{h: [("call", 0.6), ("fold", 0.4)] for h in [
        "99", "88", "77", "66",
    ]},
}


def lookup(
    chart: dict[str, list[tuple[str, float]]],
    hand: str,
) -> list[tuple[str, float]]:
    """Return the action distribution for `hand` in `chart`. Default: fold."""
    return chart.get(hand, [("fold", 1.0)])
