from typing import Literal, Union
from pydantic import BaseModel


class Action(BaseModel):
    kind: Literal["fold", "check_call", "raise_to"]
    amount: int = 0


class HandStart(BaseModel):
    type: Literal["hand_start"] = "hand_start"
    hand_id: int
    button_seat: int
    blinds: tuple[int, int]
    seats: list["SeatInfo"]


class SeatInfo(BaseModel):
    seat: int
    bot_name: str
    starting_stack: int
    hole_cards: list[str]


class ActorTurn(BaseModel):
    type: Literal["actor_turn"] = "actor_turn"
    seat: int
    to_call: int
    min_raise: int
    max_raise: int


class ActionEvent(BaseModel):
    type: Literal["action"] = "action"
    seat: int
    bot_name: str
    action: Action
    pot: int
    stacks: list[int]
    bets: list[int]


class StreetDeal(BaseModel):
    type: Literal["street_deal"] = "street_deal"
    street: Literal["flop", "turn", "river"]
    board: list[str]


class Showdown(BaseModel):
    type: Literal["showdown"] = "showdown"
    hole_cards: dict[int, list[str]]


class HandEnd(BaseModel):
    type: Literal["hand_end"] = "hand_end"
    hand_id: int
    payoffs: dict[int, int]
    final_stacks: list[int]
    board: list[str]


class LeaderboardEntry(BaseModel):
    bot_name: str
    hands_played: int
    net_chips: int


class LeaderboardUpdate(BaseModel):
    type: Literal["leaderboard"] = "leaderboard"
    entries: list[LeaderboardEntry]


class Snapshot(BaseModel):
    """Sent on websocket connect so a late viewer can render the current table."""
    type: Literal["snapshot"] = "snapshot"
    bots: list[str]
    leaderboard: list[LeaderboardEntry]
    in_hand: bool
    current_hand_id: int | None = None


Event = Union[
    HandStart,
    ActorTurn,
    ActionEvent,
    StreetDeal,
    Showdown,
    HandEnd,
    LeaderboardUpdate,
    Snapshot,
]
