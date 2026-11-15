from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class PreAdmissionView:
    """Immutable pre-admission snapshot; never includes realized response data."""

    request_id: str
    timestamp: str
    tenant: str
    provider: str
    model: str
    input_tokens: int
    cached_input_tokens: int
    input_cost: int
    output_price: int
    estimated_cost: int


@dataclass(frozen=True, slots=True)
class ObservableState:
    """Observable state snapshot seen by policies; no future or realized data."""

    global_remaining: int
    tenant_remaining: Mapping[str, int]
    tenant_spent: Mapping[str, int]
    historical_spend: Mapping[str, int]
    counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_remaining", MappingProxyType(dict(self.tenant_remaining)))
        object.__setattr__(self, "tenant_spent", MappingProxyType(dict(self.tenant_spent)))
        object.__setattr__(self, "historical_spend", MappingProxyType(dict(self.historical_spend)))
        object.__setattr__(self, "counts", MappingProxyType(dict(self.counts)))

    @property
    def historical_spent(self) -> Mapping[str, int]:
        return self.historical_spend
