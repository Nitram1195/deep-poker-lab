"""GameRunner — runs hand after hand forever, calls bots, broadcasts events."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from backend.bots.base import Bot
from backend.engine import HandEngine
from backend.events import (
    ActionEvent,
    ActorTurn,
    HandEnd,
    HandStart,
    LeaderboardEntry,
    LeaderboardUpdate,
    SeatInfo,
    Showdown,
    StreetDeal,
)
from backend.observation import build_observation

log = logging.getLogger(__name__)

Broadcast = Callable[[Any], Awaitable[None]]


# Pause durations so a human can follow the action in the browser.
ACTION_DELAY_S = 0.8
STREET_DELAY_S = 1.2
HAND_END_DELAY_S = 2.5


class GameRunner:
    def __init__(
        self,
        bots: list[Bot],
        broadcast: Broadcast,
        starting_stack: int = 200,
        blinds: tuple[int, int] = (1, 2),
    ):
        if len(bots) < 2:
            raise ValueError("need at least 2 bots")
        self._bots = bots
        self._broadcast = broadcast
        self._starting_stack = starting_stack
        self._blinds = blinds
        self._hand_id = 0
        self._lifetime_pnl: dict[str, int] = {b.name: 0 for b in bots}
        self._hands_played: dict[str, int] = {b.name: 0 for b in bots}
        self._task: asyncio.Task[None] | None = None

    @property
    def in_hand(self) -> bool:
        return self._task is not None and not self._task.done()

    def leaderboard(self) -> list[LeaderboardEntry]:
        return [
            LeaderboardEntry(
                bot_name=b.name,
                hands_played=self._hands_played[b.name],
                net_chips=self._lifetime_pnl[b.name],
            )
            for b in self._bots
        ]

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_forever(), name="game-runner")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_forever(self) -> None:
        try:
            while True:
                await self._play_one_hand()
                await asyncio.sleep(HAND_END_DELAY_S)
        except asyncio.CancelledError:
            log.info("game runner cancelled")
            raise
        except Exception:
            log.exception("game runner crashed")
            raise

    async def _play_one_hand(self) -> None:
        n = len(self._bots)
        # Rotate seating: button rotates one seat per hand. With pokerkit player_count=n,
        # seat n-1 is the button, so by rotating bot_for_seat we rotate which bot has
        # the button.
        rotation = self._hand_id % n
        bot_for_seat = [self._bots[(rotation + i) % n] for i in range(n)]

        engine = HandEngine(
            player_count=n,
            starting_stacks=[self._starting_stack] * n,
            blinds=self._blinds,
        )
        button_seat = n - 1
        self._hand_id += 1

        await self._broadcast(
            HandStart(
                hand_id=self._hand_id,
                button_seat=button_seat,
                blinds=self._blinds,
                seats=[
                    SeatInfo(
                        seat=i,
                        bot_name=bot_for_seat[i].name,
                        starting_stack=self._starting_stack,
                        hole_cards=list(engine.hole_cards(i)),
                    )
                    for i in range(n)
                ],
            )
        )

        last_street = -1
        while not engine.is_complete():
            actor = engine.current_actor()
            if actor is None:
                # All automations are on; if status is True but no actor, the engine
                # is mid-transition. This shouldn't happen in NLHE cash games, but if
                # it does we don't want to spin or read stale payoffs.
                break

            # Detect that the engine auto-dealt a new street between actions.
            cur_street = engine.street_index()
            if cur_street != last_street and cur_street > 0 and engine.board_cards():
                street_name = ("flop", "turn", "river")[min(cur_street - 1, 2)]
                await self._broadcast(
                    StreetDeal(street=street_name, board=engine.board_cards())
                )
                await asyncio.sleep(STREET_DELAY_S)
            last_street = cur_street

            legal = engine.legal_actions()
            await self._broadcast(
                ActorTurn(
                    seat=actor,
                    to_call=legal.to_call,
                    min_raise=legal.min_raise,
                    max_raise=legal.max_raise,
                )
            )

            obs = build_observation(engine, actor, button_seat, self._blinds)
            try:
                action = bot_for_seat[actor].act(obs)
            except Exception:
                log.exception("bot %s crashed; folding for it", bot_for_seat[actor].name)
                from backend.events import Action
                action = Action(kind="check_call") if legal.can_check_call else Action(kind="fold")

            engine.apply(action)

            await self._broadcast(
                ActionEvent(
                    seat=actor,
                    bot_name=bot_for_seat[actor].name,
                    action=action,
                    pot=engine.pot() + sum(engine.bets()),
                    stacks=engine.stacks(),
                    bets=engine.bets(),
                )
            )
            await asyncio.sleep(ACTION_DELAY_S)

        # Hand finished: reveal hole cards of any non-folded seats, broadcast end.
        folded = engine.folded()
        revealed = {
            i: list(engine.hole_cards(i)) for i in range(n) if not folded[i]
        }
        if len(revealed) > 1:
            await self._broadcast(Showdown(hole_cards=revealed))

        payoffs = engine.payoffs()
        for i, bot in enumerate(bot_for_seat):
            self._lifetime_pnl[bot.name] += payoffs[i]
            self._hands_played[bot.name] += 1

        await self._broadcast(
            HandEnd(
                hand_id=self._hand_id,
                payoffs={i: payoffs[i] for i in range(n)},
                final_stacks=engine.stacks(),
                board=engine.board_cards(),
            )
        )
        await self._broadcast(LeaderboardUpdate(entries=self.leaderboard()))
