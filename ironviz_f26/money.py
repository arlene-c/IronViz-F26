from __future__ import annotations

from numbers import Integral


class Money:
    """Utility helpers for pricing in integer micro-USD."""

    @staticmethod
    def cost_for_tokens(tokens: int, price_per_million: int) -> int:
        if any(isinstance(v, bool) or not isinstance(v, Integral) for v in (tokens, price_per_million)):
            raise ValueError("tokens and prices must be integers")
        if tokens < 0:
            raise ValueError("tokens must be non-negative")
        if price_per_million < 0:
            raise ValueError("price_per_million must be non-negative")
        return (int(tokens) * int(price_per_million) + 999_999) // 1_000_000
