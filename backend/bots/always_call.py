from backend.bots.base import Observation
from backend.events import Action


class AlwaysCallBot:
    name = "AlwaysCall"

    def act(self, obs: Observation) -> Action:
        if obs.can_check_call:
            return Action(kind="check_call")
        return Action(kind="fold")
