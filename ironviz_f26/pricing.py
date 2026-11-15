from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple


@dataclass(frozen=True, slots=True)
class PriceRecord:
    provider: str
    model: str
    input_price: int
    cached_input_price: int
    output_price: int


class PriceCatalog:
    """Versioned catalog keyed by provider/model."""

    def __init__(self, version: str, rows: Mapping[Tuple[str, str], PriceRecord]):
        self.version = version
        self._rows = dict(rows)

    def lookup(self, provider: str, model: str) -> PriceRecord:
        try:
            return self._rows[(provider, model)]
        except KeyError as exc:
            raise KeyError(f"No pricing record for {provider}/{model} in catalog {self.version}") from exc

    def __contains__(self, pair: tuple[str, str]) -> bool:
        return pair in self._rows
