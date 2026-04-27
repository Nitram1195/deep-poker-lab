"""Build a per-bot Observation from the current engine state."""
from backend.bots.base import Observation
from backend.engine import HandEngine


def build_observation(engine: HandEngine, seat: int, button_seat: int, blinds: tuple[int, int]) -> Observation:
    legal = engine.legal_actions()
    return Observation(
        hole_cards=engine.hole_cards(seat),
        board=engine.board_cards(),
        pot=engine.pot(),
        street=engine.street_index(),
        seat=seat,
        button_seat=button_seat,
        stacks=engine.stacks(),
        bets=engine.bets(),
        folded=engine.folded(),
        to_call=legal.to_call,
        min_raise=legal.min_raise,
        max_raise=legal.max_raise,
        blinds=blinds,
        can_check_call=legal.can_check_call,
        can_raise=legal.can_raise,
    )
