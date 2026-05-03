"""Per-opponent rolling counters used to bias the range model.

Tracks Voluntarily Put In Pot (VPIP) and Pre-Flop Raise (PFR) frequencies
across hands. A loose opponent (high VPIP, low PFR) calls with a wider range
than the default 40%; a nit (low VPIP/PFR) tightens. This isn't deep
opponent modeling — it's just enough signal to not treat all opponents
identically.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OpponentStats:
    name: str
    hands_seen: int = 0
    vpip_count: int = 0    # voluntarily put in pot at least once preflop
    pfr_count: int = 0     # raised at least once preflop
    # per-current-hand flags so we count each hand once
    _vpip_this_hand: bool = field(default=False, repr=False)
    _pfr_this_hand: bool = field(default=False, repr=False)

    def begin_hand(self) -> None:
        self._vpip_this_hand = False
        self._pfr_this_hand = False

    def observe_action(self, street: str, kind: str) -> None:
        if street != "preflop":
            return
        if kind == "raise_to":
            if not self._pfr_this_hand:
                self.pfr_count += 1
                self._pfr_this_hand = True
            if not self._vpip_this_hand:
                self.vpip_count += 1
                self._vpip_this_hand = True
        elif kind == "check_call":
            # only counts as VPIP if there was a bet to call (i.e. they didn't just check the BB)
            # we approximate by counting all check_call as VPIP — over many hands it averages out
            if not self._vpip_this_hand:
                self.vpip_count += 1
                self._vpip_this_hand = True

    def end_hand(self) -> None:
        self.hands_seen += 1

    @property
    def vpip(self) -> float:
        if self.hands_seen < 5:
            return 0.30  # default before sample size kicks in
        return self.vpip_count / self.hands_seen

    @property
    def pfr(self) -> float:
        if self.hands_seen < 5:
            return 0.18
        return self.pfr_count / self.hands_seen


class OpponentBook:
    """Maps bot_name -> OpponentStats. Updated externally by the GTOBot's
    bookkeeping pass each time it is asked to act."""

    def __init__(self) -> None:
        self._by_name: dict[str, OpponentStats] = {}
        self._last_seen_history_len: int = 0
        self._last_hand_id: int | None = None

    def get(self, name: str) -> OpponentStats:
        if name not in self._by_name:
            self._by_name[name] = OpponentStats(name=name)
        return self._by_name[name]

    def update_from_history(self, history) -> None:
        """Fold in newly-observed actions from `obs.action_history`. The bot
        calls this each turn; we replay only the entries we haven't seen."""
        for h in history[self._last_seen_history_len :]:
            stats = self.get(h.bot_name)
            if not stats._vpip_this_hand and not stats._pfr_this_hand:
                stats.begin_hand()
            stats.observe_action(h.street, h.kind)
        self._last_seen_history_len = len(history)

    def end_hand(self) -> None:
        for stats in self._by_name.values():
            stats.end_hand()
        self._last_seen_history_len = 0

    def hand_id_seen(self, hand_id: int) -> bool:
        """Idempotent end-of-hand bookkeeping: returns True if we've already
        ended this hand in our records. The runner doesn't tell bots
        when a hand is over, so the bot calls this on the *next* hand to
        finalize counters."""
        if self._last_hand_id is None:
            self._last_hand_id = hand_id
            return False
        if self._last_hand_id != hand_id:
            self.end_hand()
            self._last_hand_id = hand_id
            return False
        return True
