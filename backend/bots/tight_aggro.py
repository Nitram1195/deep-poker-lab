"""Hand-tuned baseline. Not good poker — just better than random.

Preflop: raise premium hands, otherwise call small bets and fold big ones.
Postflop: bet half-pot with top pair or better, otherwise check/fold.
"""
from backend.bots.base import Observation
from backend.events import Action


_RANK_VALUE = {r: i for i, r in enumerate("23456789TJQKA")}


def _rank(card: str) -> str:
    return card[0]


def _suit(card: str) -> str:
    return card[1]


def _is_premium_pair(c1: str, c2: str) -> bool:
    return _rank(c1) == _rank(c2) and _RANK_VALUE[_rank(c1)] >= _RANK_VALUE["T"]


def _is_big_ace(c1: str, c2: str) -> bool:
    ranks = {_rank(c1), _rank(c2)}
    return "A" in ranks and (ranks & {"K", "Q"})


def _is_playable_pair(c1: str, c2: str) -> bool:
    return _rank(c1) == _rank(c2)


def _is_suited_connector(c1: str, c2: str) -> bool:
    if _suit(c1) != _suit(c2):
        return False
    a, b = sorted([_RANK_VALUE[_rank(c1)], _RANK_VALUE[_rank(c2)]])
    return b - a == 1 and a >= _RANK_VALUE["6"]


def _has_top_pair_or_better(hole: tuple[str, str], board: list[str]) -> bool:
    if not board:
        return _rank(hole[0]) == _rank(hole[1])
    board_ranks = [_rank(c) for c in board]
    top_board_rank_value = max(_RANK_VALUE[r] for r in board_ranks)
    hole_ranks = [_rank(c) for c in hole]
    # pocket pair higher than board top → overpair
    if hole_ranks[0] == hole_ranks[1] and _RANK_VALUE[hole_ranks[0]] > top_board_rank_value:
        return True
    # one of our cards matches the highest board card → top pair
    top_rank = max(board_ranks, key=lambda r: _RANK_VALUE[r])
    if top_rank in hole_ranks:
        return True
    # paired board with our pocket pair → two pair (rough)
    if hole_ranks[0] == hole_ranks[1] and hole_ranks[0] in board_ranks:
        return True
    return False


class TightAggroRuleBot:
    name = "TightAggro"

    def act(self, obs: Observation) -> Action:
        c1, c2 = obs.hole_cards
        bb = obs.blinds[1]

        # ---- preflop ----
        if obs.street == 0:
            premium = _is_premium_pair(c1, c2) or _is_big_ace(c1, c2)
            playable = _is_playable_pair(c1, c2) or _is_suited_connector(c1, c2)

            if premium:
                # raise 3bb over the current to_call
                target = max(obs.min_raise, 3 * bb)
                target = min(target, obs.max_raise)
                if obs.can_raise:
                    return Action(kind="raise_to", amount=target)
                return Action(kind="check_call")

            # not premium: call small bets, fold to anything bigger than 3bb
            if obs.to_call == 0:
                return Action(kind="check_call")
            if playable and obs.to_call <= 3 * bb:
                return Action(kind="check_call")
            return Action(kind="fold")

        # ---- postflop ----
        strong = _has_top_pair_or_better(obs.hole_cards, obs.board)
        pot = obs.pot + sum(obs.bets)

        if strong:
            if obs.can_raise:
                target = max(obs.min_raise, pot // 2 + obs.to_call)
                target = min(target, obs.max_raise)
                return Action(kind="raise_to", amount=target)
            return Action(kind="check_call")

        if obs.to_call == 0:
            return Action(kind="check_call")
        # fold to any bet without strong hand
        return Action(kind="fold")
