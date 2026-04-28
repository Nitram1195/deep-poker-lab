from backend.bots.base import Observation
from backend.events import Action


class AlwaysFoldBot:
    name = "AlwaysFold"

    def act(self, obs: Observation) -> Action:
        # Folding when we could check for free isn't legal; check in that case.
        if obs.to_call <= 0:
            return Action(kind="check_call")
        return Action(kind="fold")
