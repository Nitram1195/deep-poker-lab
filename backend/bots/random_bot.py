import random

from backend.bots.base import Bot, Observation
from backend.events import Action


class RandomBot:
    name = "Random"

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def act(self, obs: Observation) -> Action:
        choices: list[Action] = []
        # Don't fold for free — it's weird and triggers pokerkit warnings.
        if obs.to_call > 0:
            choices.append(Action(kind="fold"))
        if obs.can_check_call:
            choices.append(Action(kind="check_call"))
        if obs.can_raise:
            # pick a uniform raise size between min and max
            amount = self._rng.randint(obs.min_raise, obs.max_raise)
            choices.append(Action(kind="raise_to", amount=amount))
        return self._rng.choice(choices)


# Bot is structural; a runtime check would be:
_: Bot = RandomBot()
