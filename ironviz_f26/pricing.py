from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple
from numbers import Integral


@dataclass(frozen=True, slots=True)
class PriceRecord:
    provider: str
    model: str
    input_price: int
    cached_input_price: int
    output_price: int

    def __post_init__(self):
        if not self.provider.strip() or not self.model.strip():
            raise ValueError("provider and model must be nonblank")
        for value in (self.input_price, self.cached_input_price, self.output_price):
            if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
                raise ValueError("prices must be non-negative integers")
        if self.cached_input_price > self.input_price:
            raise ValueError("cached-input price exceeds input price")


class PriceCatalog:
    """Versioned catalog keyed by provider/model."""

    def __init__(self, version: str, rows: Mapping[Tuple[str, str], PriceRecord]):
        self.version = version
        self._rows = dict(rows)
        if not str(version).strip():
            raise ValueError("catalog version must be nonblank")
        if any(pair != (record.provider, record.model) for pair, record in self._rows.items()):
            raise ValueError("catalog keys must match record provider/model pairs")

    def lookup(self, provider: str, model: str) -> PriceRecord:
        try:
            return self._rows[(provider, model)]
        except KeyError as exc:
            raise KeyError(f"No pricing record for {provider}/{model} in catalog {self.version}") from exc

    def __contains__(self, pair: tuple[str, str]) -> bool:
        return pair in self._rows
