"""GTOBot — chart-driven preflop, range-based postflop, MDF-correct mixing.

Pipeline per decision:
  1. Detect position and preflop scenario (open / vs-raise / vs-3bet).
  2. Preflop: look up the chart entry for our hand class, sample an action
     from the mixed distribution.
  3. Postflop: build a weighted range for each opponent based on their
     observed actions; Monte-Carlo our equity vs those ranges; combine
     with pot odds (folds), value-bet sizing keyed to board texture, and
     a bluff frequency derived from MDF.
"""
from __future__ import annotations

import random

from pokerkit import Card, StandardHighHand

from backend.bots.base import Observation
from backend.bots.gto import mdf
from backend.bots.gto.preflop_charts import (
    OPEN_BY_POSITION,
    VS_RAISE_DEFAULT,
    VS_THREE_BET_DEFAULT,
    hand_class,
    lookup,
    position_label,
)
from backend.bots.gto.range_model import OpponentRange
from backend.bots.gto.texture import texture
from backend.events import Action

_DECK_BY_STR: dict[str, Card] = {
    f"{c.rank}{c.suit}": c
    for c in Card.parse("".join(r + s for r in "23456789TJQKA" for s in "shdc"))
}


class GTOBot:
    name = "GTO"

    def __init__(self, seed: int | None = None, mc_sims: int = 200):
        self._rng = random.Random(seed)
        self._mc_sims = mc_sims

    # -------- Entry point --------

    def act(self, obs: Observation) -> Action:
        if obs.street == 0:
            return self._preflop(obs)
        return self._postflop(obs)

    # -------- Preflop --------

    def _preflop(self, obs: Observation) -> Action:
        n_active = len(obs.stacks)
        position = position_label(obs.seat, obs.button_seat, n_active)

        prior_raises_by_others = sum(
            1 for h in obs.action_history
            if h.kind == "raise_to" and h.street == "preflop" and h.seat != obs.seat
        )
        our_raises = sum(
            1 for h in obs.action_history
            if h.kind == "raise_to" and h.street == "preflop" and h.seat == obs.seat
        )

        if prior_raises_by_others == 0:
            scenario = "open"
            chart = OPEN_BY_POSITION.get(position, OPEN_BY_POSITION["BTN"])
        elif our_raises >= 1 and prior_raises_by_others >= 1:
            scenario = "vs_3bet"
            chart = VS_THREE_BET_DEFAULT
        else:
            scenario = "vs_raise"
            chart = VS_RAISE_DEFAULT

        hand = hand_class(obs.hole_cards[0], obs.hole_cards[1])
        dist = lookup(chart, hand)
        label = self._sample(dist)
        return self._make_preflop_action(label, obs, scenario)

    def _make_preflop_action(self, label: str, obs: Observation, scenario: str) -> Action:
        bb = obs.blinds[1]
        if label == "fold":
            if obs.to_call <= 0:
                return Action(kind="check_call")
            return Action(kind="fold")
        if label == "call":
            return Action(kind="check_call") if obs.can_check_call else Action(kind="fold")
        if label == "open":
            target = max(obs.min_raise, 3 * bb)
            return self._raise_to(obs, target)
        # 3-bet: ~3x the prior raise; 4-bet: ~2.5x
        prior = max(
            (h.amount for h in obs.action_history
             if h.kind == "raise_to" and h.street == "preflop"),
            default=bb,
        )
        if label == "three_bet":
            target = max(obs.min_raise, 3 * prior)
        elif label == "four_bet":
            target = max(obs.min_raise, int(2.4 * prior))
        else:
            return Action(kind="check_call") if obs.can_check_call else Action(kind="fold")
        return self._raise_to(obs, target)

    # -------- Postflop --------

    def _postflop(self, obs: Observation) -> Action:
        opp_ranges = self._build_opponent_ranges(obs)
        equity = self._equity_vs_ranges(obs, opp_ranges)

        pot_total = obs.pot + sum(obs.bets)
        pot_odds = obs.to_call / (pot_total + obs.to_call) if obs.to_call > 0 else 0.0
        tex = texture(obs.board)
        margin = 0.04

        # 1. Fold against bets we don't have equity for.
        if obs.to_call > 0 and equity < pot_odds + margin:
            return Action(kind="fold")

        # 2. Value-bet / value-raise when we have an edge.
        if obs.can_raise:
            target = self._value_bet_target(obs, equity, tex)
            if target is not None:
                return self._raise_to(obs, target)

        # 3. Bluff occasionally — only with low-equity hands (no showdown value).
        #    Frequency keyed to MDF: on a half-pot bet the right value:bluff
        #    ratio is 3:1, so bluffs are ~25% of betting range.
        if obs.to_call == 0 and obs.can_raise and equity < 0.28:
            bluff_p = self._bluff_probability(obs, tex)
            if self._rng.random() < bluff_p:
                target = self._bluff_target(obs, tex)
                return self._raise_to(obs, target)

        # 4. Default: check / call.
        return Action(kind="check_call") if obs.can_check_call else Action(kind="fold")

    def _value_bet_target(self, obs: Observation, equity: float, tex) -> int | None:
        """Pick a bet/raise size keyed to equity and board wetness. Returns the
        raise-to amount, or None if we shouldn't bet for value."""
        pot_total = obs.pot + sum(obs.bets)
        if equity > 0.80:
            mult = 1.0 if tex.wetness >= 2 else 0.75
        elif equity > 0.65:
            mult = 0.66 if tex.wetness >= 2 else 0.5
        elif equity > 0.55:
            mult = 0.5 if tex.wetness >= 2 else 0.33
        else:
            return None
        return int(mult * pot_total) + obs.to_call

    def _bluff_probability(self, obs: Observation, tex) -> float:
        """Probability of bluffing given a clean check-line (to_call == 0).

        On a dry, paired, or king/ace-high board our bluffs work more often
        because opponent has fewer hands they can continue with. Tone down on
        wet, low boards where the field has many continues. River bluffs are
        rarer than flop c-bets — fewer cards to come, no bluff equity left."""
        base = 0.32
        if tex.wetness >= 2:
            base *= 0.5
        if tex.high_card >= 11:  # K or A high → range-favoring board
            base *= 1.15
        if obs.street == 3:  # river
            base *= 0.6
        return min(0.5, base)

    def _bluff_target(self, obs: Observation, tex) -> int:
        """Pick a bluff size matching what we'd value-bet for balance."""
        pot_total = obs.pot + sum(obs.bets)
        mult = 0.66 if tex.wetness >= 2 else 0.5
        return int(mult * pot_total) + obs.to_call

    # -------- Range modeling --------

    def _build_opponent_ranges(self, obs: Observation) -> dict[int, OpponentRange]:
        used_cards = set(obs.hole_cards) | set(obs.board)
        n_active = len(obs.stacks)
        ranges: dict[int, OpponentRange] = {}
        for i in range(n_active):
            if i == obs.seat or obs.folded[i]:
                continue
            preflop = [
                h for h in obs.action_history if h.seat == i and h.street == "preflop"
            ]
            raised_pre = any(h.kind == "raise_to" for h in preflop)
            called_pre = any(h.kind == "check_call" for h in preflop)
            if raised_pre:
                tightness = 0.18
            elif called_pre:
                tightness = 0.45
            else:
                # Didn't act preflop (e.g. BB checked back) — wide.
                tightness = 0.85

            # Postflop actions narrow further (rough heuristic; not a real solver).
            for street_name in ("flop", "turn", "river"):
                acted_this_street = [h for h in obs.action_history
                                     if h.seat == i and h.street == street_name]
                if not acted_this_street:
                    break
                if any(h.kind == "raise_to" for h in acted_this_street):
                    tightness *= 0.55  # bet/raise → top of remaining range
                elif any(h.kind == "check_call" for h in acted_this_street):
                    tightness *= 0.85  # call → modest narrow

            r = OpponentRange(dead_cards=used_cards)
            r.narrow_to_top(tightness)
            ranges[i] = r
        return ranges

    def _equity_vs_ranges(
        self, obs: Observation, opp_ranges: dict[int, OpponentRange]
    ) -> float:
        if not opp_ranges:
            return 1.0
        hero = [_DECK_BY_STR[c] for c in obs.hole_cards]
        known_board = [_DECK_BY_STR[c] for c in obs.board]
        n_board_to_come = 5 - len(known_board)

        wins = 0.0
        valid_sims = 0
        for _ in range(self._mc_sims):
            used = set(obs.hole_cards) | set(obs.board)
            opp_combos: dict[int, tuple[str, str]] = {}
            ok = True
            # Sample one combo per opponent, avoiding card collisions.
            for opp_seat, opp_range in opp_ranges.items():
                combo = self._sample_compatible_combo(opp_range, used)
                if combo is None:
                    ok = False
                    break
                opp_combos[opp_seat] = combo
                used.add(combo[0])
                used.add(combo[1])
            if not ok:
                continue
            remaining = [c for c in _DECK_BY_STR if c not in used]
            self._rng.shuffle(remaining)
            board_extra = remaining[:n_board_to_come]
            full_board = known_board + [_DECK_BY_STR[c] for c in board_extra]
            hero_eval = StandardHighHand.from_game(hero, full_board)
            best_opp = max(
                StandardHighHand.from_game(
                    [_DECK_BY_STR[c] for c in opp_combos[s]], full_board
                )
                for s in opp_combos
            )
            if hero_eval > best_opp:
                wins += 1.0
            elif not (hero_eval < best_opp):
                wins += 0.5
            valid_sims += 1
        return wins / valid_sims if valid_sims else 0.5

    def _sample_compatible_combo(
        self, opp_range: OpponentRange, used: set[str]
    ) -> tuple[str, str] | None:
        for _ in range(20):
            combo = opp_range.sample(self._rng)
            if combo is None:
                return None
            if combo[0] not in used and combo[1] not in used:
                return combo
        return None  # gave up — range too card-collision-heavy

    # -------- Helpers --------

    def _raise_to(self, obs: Observation, target: int) -> Action:
        if not obs.can_raise:
            return Action(kind="check_call") if obs.can_check_call else Action(kind="fold")
        target = max(obs.min_raise, min(obs.max_raise, target))
        return Action(kind="raise_to", amount=target)

    def _sample(self, dist: list[tuple[str, float]]) -> str:
        total = sum(p for _, p in dist) or 1.0
        r = self._rng.random() * total
        cum = 0.0
        for label, p in dist:
            cum += p
            if r <= cum:
                return label
        return dist[-1][0]
