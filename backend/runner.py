"""GameRunner — runs hand after hand forever, calls bots, broadcasts events."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from backend.bots.base import Bot, HistoryEntry
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
TURN_DELAY_S = 0.7        # actor's seat is highlighted for this long before they act
ACTION_DELAY_S = 1.2      # how long the action stays on screen after it's taken
STREET_DELAY_S = 1.5      # pause after new community cards are dealt
HAND_END_DELAY_S = 3.0    # pause between hands


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
        # Each bot has a fixed UI seat (its index in self._bots) so the table is
        # stable across hands. The engine-side seat rotates: pokerkit's button is
        # always engine seat n-1, so we reassign which bot sits at engine seat n-1
        # each hand. Everything that goes out over the WS is in UI-seat space.
        rotation = self._hand_id % n
        bot_for_seat = [self._bots[(rotation + i) % n] for i in range(n)]
        # engine seat e -> UI seat
        e2u = [(rotation + e) % n for e in range(n)]

        def list_e2u(values: list) -> list:
            out = [None] * n
            for e in range(n):
                out[e2u[e]] = values[e]
            return out

        def dict_e2u(d: dict) -> dict:
            return {e2u[e]: v for e, v in d.items()}

        engine = HandEngine(
            player_count=n,
            starting_stacks=[self._starting_stack] * n,
            blinds=self._blinds,
        )
        button_engine_seat = n - 1
        button_ui_seat = e2u[button_engine_seat]
        self._hand_id += 1

        await self._broadcast(
            HandStart(
                hand_id=self._hand_id,
                button_seat=button_ui_seat,
                blinds=self._blinds,
                seats=[
                    SeatInfo(
                        seat=u,
                        bot_name=self._bots[u].name,
                        starting_stack=self._starting_stack,
                        hole_cards=list(engine.hole_cards((u - rotation) % n)),
                    )
                    for u in range(n)
                ],
            )
        )

        last_street = -1
        actions_this_hand: list[HistoryEntry] = []
        street_names = ("preflop", "flop", "turn", "river")
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
                    StreetDeal(
                        street=street_name,
                        board=engine.board_cards(),
                        hand_labels=dict_e2u(engine.hand_labels_by_seat()),
                    )
                )
                await asyncio.sleep(STREET_DELAY_S)
            last_street = cur_street

            legal = engine.legal_actions()
            await self._broadcast(
                ActorTurn(
                    seat=e2u[actor],
                    to_call=legal.to_call,
                    min_raise=legal.min_raise,
                    max_raise=legal.max_raise,
                )
            )
            # Give the viewer time to register *whose* turn it is before
            # the action lands. (For sync bots this is a pure UX delay; for
            # the equity bot most of its 280ms compute slots in here.)
            await asyncio.sleep(TURN_DELAY_S)

            obs = build_observation(
                engine, actor, button_engine_seat, self._blinds, action_history=actions_this_hand
            )
            try:
                action = bot_for_seat[actor].act(obs)
            except Exception:
                log.exception("bot %s crashed; folding for it", bot_for_seat[actor].name)
                from backend.events import Action
                action = Action(kind="check_call") if legal.can_check_call else Action(kind="fold")

            street_at_action = engine.street_index()
            engine.apply(action)
            actions_this_hand.append(
                HistoryEntry(
                    street=street_names[min(street_at_action, 3)],
                    seat=actor,
                    bot_name=bot_for_seat[actor].name,
                    kind=action.kind,
                    amount=action.amount,
                )
            )

            await self._broadcast(
                ActionEvent(
                    seat=e2u[actor],
                    bot_name=bot_for_seat[actor].name,
                    action=action,
                    pot=engine.pot() + sum(engine.bets()),
                    stacks=list_e2u(engine.stacks()),
                    bets=list_e2u(engine.bets()),
                )
            )
            await asyncio.sleep(ACTION_DELAY_S)

        # Hand finished: reveal hole cards of any non-folded seats, broadcast end.
        folded = engine.folded()
        revealed = {
            e2u[i]: list(engine.hole_cards(i)) for i in range(n) if not folded[i]
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
                payoffs={e2u[i]: payoffs[i] for i in range(n)},
                final_stacks=list_e2u(engine.stacks()),
                board=engine.board_cards(),
                hand_labels=dict_e2u(engine.hand_labels_by_seat()),
            )
        )
        await self._broadcast(LeaderboardUpdate(entries=self.leaderboard()))
