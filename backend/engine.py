"""Thin wrapper over pokerkit. One instance = one hand."""
from collections import Counter
from dataclasses import dataclass

from pokerkit import Automation, Card, Mode, NoLimitTexasHoldem, StandardHighHand, State

from backend.events import Action, HandLabel

_DECK_BY_STR: dict[str, Card] = {
    f"{c.rank}{c.suit}": c
    for c in Card.parse("".join(r + s for r in "23456789TJQKA" for s in "shdc"))
}

_RANK_ORDER = {r: i for i, r in enumerate("23456789TJQKA")}


def _rank_word(rank: str, plural: bool = False) -> str:
    """'A' -> 'A' / 'As'; 'T' -> '10' / '10s'; '8' -> '8' / '8s'."""
    base = "10" if rank == "T" else rank
    return base + "s" if plural else base


def _describe(hand) -> str:
    """Human-friendly hand description: 'Pair of 8s', 'Aces full of Ks', etc."""
    category = hand.entry.label.value
    ranks = [c.rank for c in hand.cards]
    counts = Counter(ranks)

    def by_count(n: int) -> list[str]:
        return sorted(
            (r for r, c in counts.items() if c == n),
            key=lambda r: _RANK_ORDER[r],
            reverse=True,
        )

    def hi() -> str:
        return _rank_word(max(ranks, key=lambda r: _RANK_ORDER[r]))

    if category == "One pair":
        return f"Pair of {_rank_word(by_count(2)[0], plural=True)}"
    if category == "Two pair":
        a, b = by_count(2)
        return f"Two pair: {_rank_word(a, plural=True)} & {_rank_word(b, plural=True)}"
    if category == "Three of a kind":
        return f"Set of {_rank_word(by_count(3)[0], plural=True)}"
    if category == "Straight":
        # The wheel A-2-3-4-5 is a 5-high straight, not A-high.
        rank_set = set(ranks)
        if rank_set == set("A2345"):
            return "5-high straight"
        return f"{hi()}-high straight"
    if category == "Flush":
        return f"{hi()}-high flush"
    if category == "Full house":
        return f"{_rank_word(by_count(3)[0], plural=True)} full of {_rank_word(by_count(2)[0], plural=True)}"
    if category == "Four of a kind":
        return f"Quad {_rank_word(by_count(4)[0], plural=True)}"
    if category == "Straight flush":
        rank_set = set(ranks)
        if rank_set == set("AKQJT"):
            return "Royal flush"
        if rank_set == set("A2345"):
            return "5-high straight flush"
        return f"{hi()}-high straight flush"
    if category == "High card":
        return f"{hi()}-high"
    return category  # fallback


def hand_label(hole: tuple[str, str], board: list[str]) -> HandLabel | None:
    """Descriptive label + category for a (hole, board) combination."""
    # pokerkit's evaluator requires hole + board >= 5.
    if len(hole) + len(board) < 5:
        return None
    try:
        h = StandardHighHand.from_game(
            [_DECK_BY_STR[c] for c in hole],
            [_DECK_BY_STR[c] for c in board],
        )
    except (ValueError, KeyError):
        return None
    return HandLabel(text=_describe(h), category=h.entry.label.value)

_AUTOMATIONS = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.CARD_BURNING,
    Automation.HOLE_DEALING,
    Automation.BOARD_DEALING,
    Automation.RUNOUT_COUNT_SELECTION,
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
)


def card_str(card) -> str:
    return f"{card.rank}{card.suit}"


@dataclass
class LegalActions:
    can_fold: bool
    can_check_call: bool
    can_raise: bool
    to_call: int
    min_raise: int
    max_raise: int


class HandEngine:
    """Drives one hand of NLHE. Seat indices are pokerkit's: 0=SB, 1=BB, ..., last=BTN."""

    def __init__(self, player_count: int, starting_stacks: list[int], blinds: tuple[int, int]):
        if len(starting_stacks) != player_count:
            raise ValueError("starting_stacks length must equal player_count")
        self.player_count = player_count
        self.blinds = blinds
        self._state: State = NoLimitTexasHoldem.create_state(
            automations=_AUTOMATIONS,
            ante_trimming_status=True,
            raw_antes=0,
            raw_blinds_or_straddles=blinds,
            min_bet=blinds[1],
            raw_starting_stacks=tuple(starting_stacks),
            player_count=player_count,
            mode=Mode.CASH_GAME,
        )
        self._starting_stacks = list(starting_stacks)

    @property
    def state(self) -> State:
        return self._state

    def current_actor(self) -> int | None:
        return self._state.actor_index

    def is_complete(self) -> bool:
        return not self._state.status

    def street_index(self) -> int:
        return self._state.street_index if self._state.street_index is not None else 3

    def board_cards(self) -> list[str]:
        out: list[str] = []
        for street_cards in self._state.board_cards:
            for card in street_cards:
                out.append(card_str(card))
        return out

    def hole_cards(self, seat: int) -> tuple[str, str]:
        cards = self._state.hole_cards[seat]
        return (card_str(cards[0]), card_str(cards[1]))

    def stacks(self) -> list[int]:
        return list(self._state.stacks)

    def bets(self) -> list[int]:
        return list(self._state.bets)

    def pot(self) -> int:
        return sum(p.amount for p in self._state.pots) if self._state.pots else 0

    def folded(self) -> list[bool]:
        return [not active for active in self._state.statuses]

    def legal_actions(self) -> LegalActions:
        s = self._state
        return LegalActions(
            can_fold=s.can_fold(),
            can_check_call=s.can_check_or_call(),
            can_raise=s.can_complete_bet_or_raise_to(),
            to_call=s.checking_or_calling_amount or 0,
            min_raise=s.min_completion_betting_or_raising_to_amount or 0,
            max_raise=s.max_completion_betting_or_raising_to_amount or 0,
        )

    def apply(self, action: Action) -> None:
        s = self._state
        if action.kind == "fold":
            if not s.can_fold():
                # nothing to fold to → treat as check
                s.check_or_call()
                return
            s.fold()
        elif action.kind == "check_call":
            s.check_or_call()
        elif action.kind == "raise_to":
            legal = self.legal_actions()
            amount = max(legal.min_raise, min(legal.max_raise, action.amount))
            s.complete_bet_or_raise_to(amount)
        else:
            raise ValueError(f"unknown action kind: {action.kind}")

    def payoffs(self) -> list[int]:
        """Per-seat chip delta for this hand (sums to 0 minus rake)."""
        return list(self._state.payoffs)

    def hand_labels_by_seat(self) -> dict[int, "HandLabel"]:
        """Hand-strength labels per non-folded seat. Empty preflop."""
        labels: dict[int, HandLabel] = {}
        folded = self.folded()
        board = self.board_cards()
        for i in range(self.player_count):
            if folded[i]:
                continue
            label = hand_label(self.hole_cards(i), board)
            if label is not None:
                labels[i] = label
        return labels
