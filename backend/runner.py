"""GameRunner — runs hand after hand forever, calls bots, broadcasts events."""
from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from backend.bots.base import Bot, HistoryEntry
from backend.engine import HandEngine, hand_label
from pydantic import BaseModel

from backend.events import (
    ActionEvent,
    ActorTurn,
    HandEnd,
    HandReplay,
    HandStart,
    HandSync,
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
        delay_scale: float = 1.0,
    ):
        if len(bots) < 2:
            raise ValueError("need at least 2 bots")
        self._bots = bots
        self._broadcast = broadcast
        self._starting_stack = starting_stack
        self._blinds = blinds
        # Multiplied into every visual sleep. Set to 0.0 for benchmark mode.
        self._delay_scale = delay_scale
        self._hand_id = 0
        self._lifetime_pnl: dict[str, int] = {b.name: 0 for b in bots}
        self._hands_played: dict[str, int] = {b.name: 0 for b in bots}
        self._vpip_count: dict[str, int] = {b.name: 0 for b in bots}
        self._pfr_count: dict[str, int] = {b.name: 0 for b in bots}
        # UI-seat indices currently sitting out. A toggle takes effect from the
        # next hand; the in-progress hand always finishes first.
        self._sitting_out: set[int] = set()
        # Set when there are enough active bots to play a hand. Used to pause
        # the runner if too many bots sit out.
        self._can_play = asyncio.Event()
        self._can_play.set()
        self._task: asyncio.Task[None] | None = None
        # Mid-hand state used to resync a client that connects mid-hand.
        self._cur_engine: HandEngine | None = None
        self._cur_seats_payload: list[SeatInfo] = []
        self._cur_e2u: list[int] = []
        self._cur_button_ui: int = 0
        self._cur_human_seats: set[int] = set()
        self._cur_actor_ui: int | None = None
        self._cur_legal: tuple[int, int, int] | None = None
        # Replay buffer for the current hand (unfiltered: all hole cards visible)
        # and the most recently completed hand.
        self._cur_replay: list[BaseModel] = []
        self._last_replay: list[BaseModel] = []
        self._last_replay_hand_id: int | None = None

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
                vpip=self._vpip_count[b.name],
                pfr=self._pfr_count[b.name],
            )
            for b in self._bots
        ]

    def build_sync(self) -> HandSync | None:
        """Snapshot of the current hand, or None if no hand is active."""
        eng = self._cur_engine
        if eng is None:
            return None
        n_total = len(self._bots)
        n_active = eng.player_count
        e2u = self._cur_e2u

        def list_to_ui(values: list, default) -> list:
            out = [default] * n_total
            for e in range(n_active):
                out[e2u[e]] = values[e]
            return out

        def dict_to_ui(d: dict) -> dict:
            return {e2u[e]: v for e, v in d.items()}

        labels = dict_to_ui(eng.hand_labels_by_seat())
        if self._cur_human_seats:
            labels = {u: lbl for u, lbl in labels.items() if u in self._cur_human_seats}

        to_call, min_raise, max_raise = self._cur_legal or (0, 0, 0)
        return HandSync(
            hand_id=self._hand_id,
            button_seat=self._cur_button_ui,
            blinds=self._blinds,
            seats=self._cur_seats_payload,
            board=eng.board_cards(),
            pot=eng.pot() + sum(eng.bets()),
            stacks=list_to_ui(eng.stacks(), self._starting_stack),
            bets=list_to_ui(eng.bets(), 0),
            folded=list_to_ui(eng.folded(), False),
            hand_labels=labels,
            current_actor=self._cur_actor_ui,
            to_call=to_call,
            min_raise=min_raise,
            max_raise=max_raise,
        )

    def build_replay(self) -> HandReplay | None:
        """Snapshot the most recently completed hand for replay, with every
        active seat's hole cards visible. Returns None if no hand finished yet."""
        if not self._last_replay or self._last_replay_hand_id is None:
            return None
        return HandReplay(
            hand_id=self._last_replay_hand_id,
            events=[ev.model_dump() for ev in self._last_replay],
        )

    async def _emit(self, ev_replay: BaseModel, ev_broadcast: BaseModel | None = None) -> None:
        """Append the unfiltered event to the replay buffer and broadcast the
        (possibly filtered) live version. If only one is given, both are equal."""
        self._cur_replay.append(ev_replay)
        await self._broadcast(ev_broadcast if ev_broadcast is not None else ev_replay)

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

    async def play_hands(self, n: int) -> None:
        """Play exactly n hands, then return. Used by benchmark mode."""
        for _ in range(n):
            await self._play_one_hand()

    async def _run_forever(self) -> None:
        try:
            while True:
                await self._can_play.wait()
                await self._play_one_hand()
                await asyncio.sleep(HAND_END_DELAY_S * self._delay_scale)
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
        human_ui_seats = {u for u in range(n_total) if getattr(self._bots[u], "is_human", False)}
        any_human = bool(human_ui_seats)

        # Reset the replay buffer for this hand (we only finalize after hand_end,
        # so an early-return up above leaves the previous hand's replay intact).
        self._cur_replay = []

        engine = HandEngine(
            player_count=n_active,
            starting_stacks=[self._starting_stack] * n_active,
            blinds=self._blinds,
        )
        # Cache hole cards now: pokerkit's HAND_KILLING automation may clear
        # losers' cards at showdown, which would prevent us from revealing them.
        hole_by_engine_seat: dict[int, list[str]] = {
            i: list(engine.hole_cards(i)) for i in range(n_active)
        }
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

        # Two seat payloads: the live (filtered) one hides opponents' cards from
        # any human at the table; the replay one shows every active hand.
        seats_payload: list[SeatInfo] = []
        seats_payload_replay: list[SeatInfo] = []
        for u in range(n_total):
            sitting_out = u in self._sitting_out
            is_human = u in human_ui_seats
            full_hole = [] if sitting_out else list(engine.hole_cards(u2e[u]))
            if sitting_out:
                live_hole = []
            elif any_human and not is_human:
                live_hole = []
            else:
                live_hole = full_hole
            base = dict(
                seat=u,
                bot_name=self._bots[u].name,
                starting_stack=self._starting_stack,
                sitting_out=sitting_out,
                is_human=is_human,
            )
            seats_payload.append(SeatInfo(hole_cards=live_hole, **base))
            seats_payload_replay.append(SeatInfo(hole_cards=full_hole, **base))

        # Stash everything resync-relevant before broadcasting hand_start.
        self._cur_engine = engine
        self._cur_seats_payload = seats_payload
        self._cur_e2u = e2u
        self._cur_button_ui = button_ui_seat
        self._cur_human_seats = human_ui_seats
        self._cur_actor_ui = None
        self._cur_legal = None

        await self._emit(
            HandStart(
                hand_id=self._hand_id,
                button_seat=button_ui_seat,
                blinds=self._blinds,
                seats=seats_payload_replay,
            ),
            HandStart(
                hand_id=self._hand_id,
                button_seat=button_ui_seat,
                blinds=self._blinds,
                seats=seats_payload,
            ),
        )

        last_street = -1
        actions_this_hand: list[HistoryEntry] = []
        street_names = ("preflop", "flop", "turn", "river")
        vpip_engine_seats: set[int] = set()
        pfr_engine_seats: set[int] = set()
        while not engine.is_complete():
            actor = engine.current_actor()
            if actor is None:
                break

            cur_street = engine.street_index()
            if cur_street != last_street and cur_street > 0 and engine.board_cards():
                street_name = ("flop", "turn", "river")[min(cur_street - 1, 2)]
                labels_unfiltered = dict_to_ui(engine.hand_labels_by_seat())
                labels_live = (
                    {u: lbl for u, lbl in labels_unfiltered.items() if u in human_ui_seats}
                    if any_human
                    else labels_unfiltered
                )
                await self._emit(
                    StreetDeal(
                        street=street_name,
                        board=engine.board_cards(),
                        hand_labels=labels_unfiltered,
                    ),
                    StreetDeal(
                        street=street_name,
                        board=engine.board_cards(),
                        hand_labels=labels_live,
                    ),
                )
                await asyncio.sleep(STREET_DELAY_S * self._delay_scale)
            last_street = cur_street

            legal = engine.legal_actions()
            self._cur_actor_ui = e2u[actor]
            self._cur_legal = (legal.to_call, legal.min_raise, legal.max_raise)
            await self._emit(
                ActorTurn(
                    seat=e2u[actor],
                    to_call=legal.to_call,
                    min_raise=legal.min_raise,
                    max_raise=legal.max_raise,
                )
            )
            await asyncio.sleep(TURN_DELAY_S * self._delay_scale)

            obs = build_observation(
                engine, actor, button_engine_seat, self._blinds, action_history=actions_this_hand
            )
            try:
                result = bot_for_engine_seat[actor].act(obs)
                action = await result if inspect.isawaitable(result) else result
            except Exception:
                log.exception("bot %s crashed; folding for it", bot_for_engine_seat[actor].name)
                from backend.events import Action
                action = Action(kind="check_call") if legal.can_check_call else Action(kind="fold")

            street_at_action = engine.street_index()
            if street_at_action == 0:
                if action.kind == "raise_to":
                    vpip_engine_seats.add(actor)
                    pfr_engine_seats.add(actor)
                elif action.kind == "check_call" and legal.to_call > 0:
                    vpip_engine_seats.add(actor)
            engine.apply(action)
            self._cur_actor_ui = None
            self._cur_legal = None
            actions_this_hand.append(
                HistoryEntry(
                    street=street_names[min(street_at_action, 3)],
                    seat=actor,
                    bot_name=bot_for_engine_seat[actor].name,
                    kind=action.kind,
                    amount=action.amount,
                )
            )

            await self._emit(
                ActionEvent(
                    seat=e2u[actor],
                    bot_name=bot_for_engine_seat[actor].name,
                    action=action,
                    pot=engine.pot() + sum(engine.bets()),
                    stacks=list_to_ui(engine.stacks(), self._starting_stack),
                    bets=list_to_ui(engine.bets(), 0),
                )
            )
            await asyncio.sleep(ACTION_DELAY_S * self._delay_scale)

        # Determine who reached showdown using our own action history rather
        # than engine.folded() — pokerkit's HAND_KILLING automation marks
        # losing hands as inactive after showdown, which would hide losers'
        # cards from the UI.
        folded_engine_seats = {h.seat for h in actions_this_hand if h.kind == "fold"}
        showdown_engine_seats = [
            i for i in range(n_active) if i not in folded_engine_seats
        ]
        is_showdown = len(showdown_engine_seats) > 1

        # Reveal cards before any auto-dealt streets so the user watches the
        # runout knowing what hands are racing.
        if is_showdown:
            revealed_ui = {
                e2u[i]: hole_by_engine_seat[i] for i in showdown_engine_seats
            }
            await self._emit(Showdown(hole_cards=revealed_ui))
            await asyncio.sleep(STREET_DELAY_S * self._delay_scale)

        # Catch up on streets that pokerkit auto-dealt during an all-in runout
        # (RUNOUT_COUNT_SELECTION). Without this, the board jumps straight from
        # whatever street the all-in happened on to the final state in HandEnd.
        final_board = engine.board_cards()
        final_street = {0: 0, 3: 1, 4: 2, 5: 3}.get(len(final_board), 0)
        if is_showdown and final_street > last_street:
            for street_idx in range(last_street + 1, final_street + 1):
                street_name = ("flop", "turn", "river")[street_idx - 1]
                board_size = (3, 4, 5)[street_idx - 1]
                partial_board = final_board[:board_size]
                labels_engine: dict[int, Any] = {}
                for i in showdown_engine_seats:
                    lbl = hand_label(tuple(hole_by_engine_seat[i]), partial_board)
                    if lbl is not None:
                        labels_engine[i] = lbl
                await self._emit(
                    StreetDeal(
                        street=street_name,
                        board=partial_board,
                        hand_labels={e2u[i]: v for i, v in labels_engine.items()},
                    )
                )
                await asyncio.sleep(STREET_DELAY_S * self._delay_scale)

        payoffs = engine.payoffs()
        for i, bot in enumerate(bot_for_engine_seat):
            self._lifetime_pnl[bot.name] += payoffs[i]
            self._hands_played[bot.name] += 1
            if i in vpip_engine_seats:
                self._vpip_count[bot.name] += 1
            if i in pfr_engine_seats:
                self._pfr_count[bot.name] += 1

        # Final hand labels for showdown participants (compute against the cached
        # hole cards in case pokerkit has mucked the loser's hand by now).
        final_labels_ui: dict[int, Any] = {}
        for i in showdown_engine_seats:
            lbl = hand_label(tuple(hole_by_engine_seat[i]), final_board)
            if lbl is not None:
                final_labels_ui[e2u[i]] = lbl

        await self._emit(
            HandEnd(
                hand_id=self._hand_id,
                payoffs={e2u[i]: payoffs[i] for i in range(n_active)},
                final_stacks=list_to_ui(engine.stacks(), self._starting_stack),
                board=final_board,
                hand_labels=final_labels_ui,
            )
        )
        await self._broadcast(LeaderboardUpdate(entries=self.leaderboard()))
        # Finalize the replay buffer for this hand.
        self._last_replay = self._cur_replay
        self._last_replay_hand_id = self._hand_id
        # Hand done — drop the resync state so a connect during the inter-hand
        # delay falls back to the next hand_start instead of replaying this one.
        self._cur_engine = None
        self._cur_actor_ui = None
        self._cur_legal = None
