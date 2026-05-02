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
    sitting_out: bool = False
    is_human: bool = False


class HandLabel(BaseModel):
    text: str       # human-friendly: "Pair of 8s", "Aces full of Ks"
    category: str   # raw pokerkit category: "One pair", "Full house" — used for color tier


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
    hand_labels: dict[int, HandLabel]


class Showdown(BaseModel):
    type: Literal["showdown"] = "showdown"
    hole_cards: dict[int, list[str]]


class HandEnd(BaseModel):
    type: Literal["hand_end"] = "hand_end"
    hand_id: int
    payoffs: dict[int, int]
    final_stacks: list[int]
    board: list[str]
    hand_labels: dict[int, HandLabel]


class LeaderboardEntry(BaseModel):
    bot_name: str
    hands_played: int
    net_chips: int


class LeaderboardUpdate(BaseModel):
    type: Literal["leaderboard"] = "leaderboard"
    entries: list[LeaderboardEntry]


class SeatsUpdate(BaseModel):
    """Pushed when a seat sits out / sits in. Takes effect from the next hand;
    the UI can still mark the seat as sitting-out immediately."""
    type: Literal["seats_update"] = "seats_update"
    sitting_out: list[int]   # UI seat indices currently flagged to sit out


class Snapshot(BaseModel):
    """Sent on websocket connect so a late viewer can render the current table."""
    type: Literal["snapshot"] = "snapshot"
    bots: list[str]
    leaderboard: list[LeaderboardEntry]
    in_hand: bool
    current_hand_id: int | None = None
    sitting_out: list[int] = []


class HandSync(BaseModel):
    """Full mid-hand state, sent to a client that connects/reconnects mid-hand."""
    type: Literal["hand_sync"] = "hand_sync"
    hand_id: int
    button_seat: int
    blinds: tuple[int, int]
    seats: list[SeatInfo]
    board: list[str]
    pot: int
    stacks: list[int]
    bets: list[int]
    folded: list[bool]
    hand_labels: dict[int, HandLabel]
    current_actor: int | None = None
    to_call: int = 0
    min_raise: int = 0
    max_raise: int = 0


Event = Union[
    HandStart,
    ActorTurn,
    ActionEvent,
    StreetDeal,
    Showdown,
    HandEnd,
    LeaderboardUpdate,
    SeatsUpdate,
    Snapshot,
    HandSync,
]
