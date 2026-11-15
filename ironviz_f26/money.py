from __future__ import annotations

import math


class Money:
    """Utility helpers for pricing in integer micro-USD."""

    @staticmethod
    def cost_for_tokens(tokens: int, price_per_million: int) -> int:
        if tokens < 0:
            raise ValueError("tokens must be non-negative")
        if price_per_million < 0:
            raise ValueError("price_per_million must be non-negative")
        return int(math.ceil((tokens * price_per_million) / 1_000_000))
