"""HumanBot — awaits an action sent by the WS client. Async act."""
from __future__ import annotations

import asyncio

from backend.bots.base import Observation
from backend.events import Action


class HumanBot:
    name = "Human"
    is_human = True

    def __init__(self) -> None:
        self._pending: asyncio.Future[Action] | None = None
        self._legal: tuple[int, int, int] | None = None  # (to_call, min_raise, max_raise)

    @property
    def waiting(self) -> bool:
        return self._pending is not None and not self._pending.done()

    async def act(self, obs: Observation) -> Action:
        loop = asyncio.get_running_loop()
        self._pending = loop.create_future()
        self._legal = (obs.to_call, obs.min_raise, obs.max_raise)
        try:
            return await self._pending
        finally:
            self._pending = None
            self._legal = None

    def submit(self, action: Action) -> bool:
        if self._pending is None or self._pending.done():
            return False
        self._pending.set_result(action)
        return True
