"""Generic LLM bot.

Works with any OpenAI-compatible endpoint (Groq, OpenAI, OpenRouter, Ollama, …).
Pass `base_url`, `api_key`, and `model`; the rest is the same code.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from backend.bots.base import Observation
from backend.events import Action

log = logging.getLogger(__name__)


_DEFAULT_PERSONALITY = (
    "You are a strong but unpredictable No-Limit Texas Hold'em player. "
    "Maximize chips over the long run. Bluff occasionally to keep opponents guessing, "
    "but pick your spots — don't bluff into multiple opponents who haven't shown weakness."
)

_STREET_NAMES = ("preflop", "flop", "turn", "river")


def _format_messages(obs: Observation, name: str, personality: str) -> list[dict[str, Any]]:
    sb, bb = obs.blinds
    n_seats = len(obs.stacks)

    seat_lines = []
    for i in range(n_seats):
        markers = []
        if i == obs.seat:
            markers.append("YOU")
        if i == obs.button_seat:
            markers.append("button")
        if obs.folded[i]:
            markers.append("folded")
        marker = f"  ({', '.join(markers)})" if markers else ""
        seat_lines.append(
            f"  seat {i}: stack={obs.stacks[i]}, bet_this_street={obs.bets[i]}{marker}"
        )

    system = (
        f'You are playing No-Limit Texas Hold\'em as a bot named "{name}" '
        f"sitting at seat {obs.seat}.\n\n"
        f"{personality}\n\n"
        "Card notation: RANK followed by SUIT (e.g. 'Ah' = ace of hearts, "
        "'Td' = ten of diamonds). RANK is one of 2,3,4,5,6,7,8,9,T,J,Q,K,A. "
        "SUIT is one of s,h,d,c.\n\n"
        "Output ONLY a single JSON object with this shape:\n"
        '  {"action": "<fold|check_call|raise_to>", "amount": <int>}\n\n'
        "Rules:\n"
        "- fold: forfeit your hand. Only legal if to_call > 0.\n"
        "- check_call: match the current bet. If to_call=0 this is a check.\n"
        "- raise_to: total amount you raise the bet to (NOT the increment). "
        "Must be in [min_raise, max_raise] inclusive.\n"
        "- amount is ignored for fold/check_call but include it (use 0).\n"
        "Do NOT add commentary outside the JSON. Do not wrap it in code fences."
    )

    user = (
        "Game state:\n"
        f"  Your hole cards: {obs.hole_cards[0]} {obs.hole_cards[1]}\n"
        f"  Board: {' '.join(obs.board) if obs.board else '(none — preflop)'}\n"
        f"  Street: {_STREET_NAMES[min(obs.street, 3)]}\n"
        f"  Collected pot (from earlier streets): {obs.pot}\n"
        f"  Current-street bets per seat: {obs.bets}\n"
        f"  Amount you must call to stay in: {obs.to_call}\n"
        f"  Legal raise-to range: [{obs.min_raise}, {obs.max_raise}]\n"
        f"  Blinds: SB={sb}, BB={bb}\n\n"
        "Seats (seat 0 = small blind, last seat = button):\n"
        + "\n".join(seat_lines)
        + "\n\nChoose your action."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


class LLMBot:
    """OpenAI-compatible LLM bot. Sync API; blocks the asyncio loop briefly per turn."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        name: str = "LLM",
        personality: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 150,
        timeout: float = 10.0,
    ):
        self.name = name
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self._model = model
        self._personality = personality or _DEFAULT_PERSONALITY
        self._temperature = temperature
        self._max_tokens = max_tokens

    def act(self, obs: Observation) -> Action:
        messages = _format_messages(obs, self.name, self._personality)
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,                                # type: ignore[arg-type]
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception:
            log.exception("LLMBot %s: API call failed; falling back", self.name)
            return self._fallback(obs)

        text = (resp.choices[0].message.content or "").strip()
        return self._parse(text, obs)

    def _parse(self, text: str, obs: Observation) -> Action:
        # Be lenient — strip leading/trailing chatter, tolerate code fences.
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.warning("LLMBot %s: non-JSON response %r", self.name, text[:200])
            return self._fallback(obs)

        kind_raw = str(data.get("action", "")).strip().lower().replace("-", "_")

        if kind_raw == "fold":
            if obs.to_call <= 0:
                # folding for free is bad form; treat as check
                return Action(kind="check_call")
            return Action(kind="fold")

        if kind_raw in ("check_call", "check", "call"):
            if obs.can_check_call:
                return Action(kind="check_call")
            return Action(kind="fold")

        if kind_raw in ("raise_to", "raise", "bet", "all_in", "allin"):
            if not obs.can_raise:
                return Action(kind="check_call") if obs.can_check_call else Action(kind="fold")
            try:
                amt = int(data.get("amount", obs.min_raise))
            except (TypeError, ValueError):
                amt = obs.min_raise
            amt = max(obs.min_raise, min(obs.max_raise, amt))
            return Action(kind="raise_to", amount=amt)

        log.warning("LLMBot %s: unknown action %r in %r", self.name, kind_raw, text[:200])
        return self._fallback(obs)

    def _fallback(self, obs: Observation) -> Action:
        if obs.can_check_call:
            return Action(kind="check_call")
        return Action(kind="fold")
