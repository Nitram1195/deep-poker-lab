"""GTO-flavored heuristic poker bot.

A solid classical bot that approximates game-theory-optimal play through
hand-tuned preflop charts, range-based postflop equity, MDF-correct value/bluff
frequencies, and texture-aware bet sizing. Not a CFR-trained solver — see the
diary for the graduation path."""
from backend.bots.gto.bot import GTOBot

__all__ = ["GTOBot"]
