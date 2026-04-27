"""Thin wrapper over pokerkit. One instance = one hand."""
from dataclasses import dataclass

from pokerkit import Automation, Mode, NoLimitTexasHoldem, State

from backend.events import Action

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
