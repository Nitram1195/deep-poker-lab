from typing import Protocol
from pydantic import BaseModel

from backend.events import Action


class HistoryEntry(BaseModel):
    street: str         # 'preflop' | 'flop' | 'turn' | 'river'
    seat: int
    bot_name: str
    kind: str           # 'fold' | 'check_call' | 'raise_to'
    amount: int = 0


class Observation(BaseModel):
    """Public view + own hole cards. What a bot sees when asked to act."""
    hole_cards: tuple[str, str]
    board: list[str]                       # 0..5 cards
    pot: int                               # collected pots only (not current street bets)
    street: int                            # 0=preflop 1=flop 2=turn 3=river
    seat: int                              # this bot's seat
    button_seat: int
    stacks: list[int]                      # by seat
    bets: list[int]                        # current-street bets by seat
    folded: list[bool]                     # by seat
    to_call: int
    min_raise: int                         # min legal raise_to amount
    max_raise: int                         # max legal raise_to amount (= all-in)
    blinds: tuple[int, int]
    can_check_call: bool
    can_raise: bool
    action_history: list[HistoryEntry] = []  # actions taken so far this hand, in order


class Bot(Protocol):
    name: str

    def act(self, obs: Observation) -> Action: ...
