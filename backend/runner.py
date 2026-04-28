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
    SeatsUpdate,
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
        # UI-seat indices currently sitting out. A toggle takes effect from the
        # next hand; the in-progress hand always finishes first.
        self._sitting_out: set[int] = set()
        # Set when there are enough active bots to play a hand. Used to pause
        # the runner if too many bots sit out.
        self._can_play = asyncio.Event()
        self._can_play.set()
        self._task: asyncio.Task[None] | None = None

    @property
    def in_hand(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def sitting_out(self) -> list[int]:
        return sorted(self._sitting_out)

    def leaderboard(self) -> list[LeaderboardEntry]:
        return [
            LeaderboardEntry(
                bot_name=b.name,
                hands_played=self._hands_played[b.name],
                net_chips=self._lifetime_pnl[b.name],
            )
            for b in self._bots
        ]

    async def set_sitting_out(self, ui_seat: int, sit_out: bool) -> None:
        if not (0 <= ui_seat < len(self._bots)):
            return
        if sit_out:
            self._sitting_out.add(ui_seat)
        else:
            self._sitting_out.discard(ui_seat)
        # Unblock the runner if we now have enough active bots.
        if len(self._bots) - len(self._sitting_out) >= 2:
            self._can_play.set()
        else:
            self._can_play.clear()
        await self._broadcast(SeatsUpdate(sitting_out=self.sitting_out))

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
                await self._can_play.wait()
                await self._play_one_hand()
                await asyncio.sleep(HAND_END_DELAY_S)
        except asyncio.CancelledError:
            log.info("game runner cancelled")
            raise
        except Exception:
            log.exception("game runner crashed")
            raise

    async def _play_one_hand(self) -> None:
        n_total = len(self._bots)
        # Snapshot which bots are active for *this* hand. Toggles after this point
        # apply to the next hand.
        active_ui = sorted(set(range(n_total)) - self._sitting_out)
        n_active = len(active_ui)
        if n_active < 2:
            self._can_play.clear()
            return

        # Map engine seat e -> UI seat. Pokerkit's button is engine seat n_active-1;
        # the SB is engine seat 0, then the rest follow in clockwise order.
        # Rotate the button through active_ui as hands go by.
        button_idx_in_active = self._hand_id % n_active
        e2u = [active_ui[(button_idx_in_active + 1 + e) % n_active] for e in range(n_active)]
        button_engine_seat = n_active - 1
        button_ui_seat = e2u[button_engine_seat]
        # Inverse for engine seat lookups by UI seat.
        u2e = {u: e for e, u in enumerate(e2u)}

        bot_for_engine_seat = [self._bots[u] for u in e2u]

        engine = HandEngine(
            player_count=n_active,
            starting_stacks=[self._starting_stack] * n_active,
            blinds=self._blinds,
        )
        self._hand_id += 1

        # Inflate engine-indexed lists/dicts to UI-seat-indexed (size n_total),
        # filling sat-out seats with safe defaults so the frontend can index by
        # UI seat without bounds-checking.
        def list_to_ui(values: list, default) -> list:
            out = [default] * n_total
            for e in range(n_active):
                out[e2u[e]] = values[e]
            return out

        def dict_to_ui(d: dict) -> dict:
            return {e2u[e]: v for e, v in d.items()}

        seats_payload: list[SeatInfo] = []
        for u in range(n_total):
            sitting_out = u in self._sitting_out
            hole_cards = [] if sitting_out else list(engine.hole_cards(u2e[u]))
            seats_payload.append(
                SeatInfo(
                    seat=u,
                    bot_name=self._bots[u].name,
                    starting_stack=self._starting_stack,
                    hole_cards=hole_cards,
                    sitting_out=sitting_out,
                )
            )

        await self._broadcast(
            HandStart(
                hand_id=self._hand_id,
                button_seat=button_ui_seat,
                blinds=self._blinds,
                seats=seats_payload,
            )
        )

        last_street = -1
        actions_this_hand: list[HistoryEntry] = []
        street_names = ("preflop", "flop", "turn", "river")
        while not engine.is_complete():
            actor = engine.current_actor()
            if actor is None:
                break

            cur_street = engine.street_index()
            if cur_street != last_street and cur_street > 0 and engine.board_cards():
                street_name = ("flop", "turn", "river")[min(cur_street - 1, 2)]
                await self._broadcast(
                    StreetDeal(
                        street=street_name,
                        board=engine.board_cards(),
                        hand_labels=dict_to_ui(engine.hand_labels_by_seat()),
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
            await asyncio.sleep(TURN_DELAY_S)

            obs = build_observation(
                engine, actor, button_engine_seat, self._blinds, action_history=actions_this_hand
            )
            try:
                action = bot_for_engine_seat[actor].act(obs)
            except Exception:
                log.exception("bot %s crashed; folding for it", bot_for_engine_seat[actor].name)
                from backend.events import Action
                action = Action(kind="check_call") if legal.can_check_call else Action(kind="fold")

            street_at_action = engine.street_index()
            engine.apply(action)
            actions_this_hand.append(
                HistoryEntry(
                    street=street_names[min(street_at_action, 3)],
                    seat=actor,
                    bot_name=bot_for_engine_seat[actor].name,
                    kind=action.kind,
                    amount=action.amount,
                )
            )

            await self._broadcast(
                ActionEvent(
                    seat=e2u[actor],
                    bot_name=bot_for_engine_seat[actor].name,
                    action=action,
                    pot=engine.pot() + sum(engine.bets()),
                    stacks=list_to_ui(engine.stacks(), self._starting_stack),
                    bets=list_to_ui(engine.bets(), 0),
                )
            )
            await asyncio.sleep(ACTION_DELAY_S)

        folded = engine.folded()
        revealed = {
            e2u[i]: list(engine.hole_cards(i)) for i in range(n_active) if not folded[i]
        }
        if len(revealed) > 1:
            await self._broadcast(Showdown(hole_cards=revealed))

        payoffs = engine.payoffs()
        for i, bot in enumerate(bot_for_engine_seat):
            self._lifetime_pnl[bot.name] += payoffs[i]
            self._hands_played[bot.name] += 1

        await self._broadcast(
            HandEnd(
                hand_id=self._hand_id,
                payoffs={e2u[i]: payoffs[i] for i in range(n_active)},
                final_stacks=list_to_ui(engine.stacks(), self._starting_stack),
                board=engine.board_cards(),
                hand_labels=dict_to_ui(engine.hand_labels_by_seat()),
            )
        )
        await self._broadcast(LeaderboardUpdate(entries=self.leaderboard()))
