from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class HindsightResult:
    benchmark: str
    selected_indices: tuple[int, ...]
    admitted_count: int
    realized_cost: int
    completion_rates: Mapping[str, float]
    label: str = "hindsight"


def _validate(costs: Sequence[int], budget: int) -> None:
    if budget < 0:
        raise ValueError("budget must be non-negative")
    if any(int(cost) < 0 for cost in costs):
        raise ValueError("realized costs must be non-negative")


def max_count_hindsight(costs: Sequence[int], budget: int) -> HindsightResult:
    """Hindsight upper bound: choose the largest count by realized cost."""
    _validate(costs, budget)
    selected: list[int] = []
    realized_cost = 0
    for index, cost in sorted(enumerate(map(int, costs)), key=lambda item: (item[1], item[0])):
        if realized_cost + cost <= budget:
            selected.append(index)
            realized_cost += cost
    return HindsightResult(
        benchmark="max_count_hindsight",
        selected_indices=tuple(sorted(selected)),
        admitted_count=len(selected),
        realized_cost=realized_cost,
        completion_rates={},
    )


def max_min_tenant_hindsight(
    tenants: Sequence[str],
    costs: Sequence[int],
    budget: int,
) -> HindsightResult:
    """Exact discrete water-filling benchmark for the minimum tenant rate.

    For each attainable minimum completion-rate breakpoint, the cheapest
    required requests are selected per tenant. The highest feasible breakpoint
    is the max-min optimum; this is a hindsight-only allocation.
    """
    if len(tenants) != len(costs):
        raise ValueError("tenants and costs must have the same length")
    _validate(costs, budget)
    grouped: dict[str, list[tuple[int, int]]] = {}
    for index, (tenant, cost) in enumerate(zip(tenants, costs)):
        grouped.setdefault(str(tenant), []).append((int(cost), index))
    if not grouped:
        return HindsightResult("max_min_tenant_hindsight", (), 0, 0, {})

    sorted_groups: dict[str, list[tuple[int, int]]] = {}
    prefix_costs: dict[str, list[int]] = {}
    for tenant, requests in grouped.items():
        ordered = sorted(requests, key=lambda item: (item[0], item[1]))
        sorted_groups[tenant] = ordered
        prefix = [0]
        for cost, _ in ordered:
            prefix.append(prefix[-1] + cost)
        prefix_costs[tenant] = prefix

    rates = {Fraction(count, len(requests)) for requests in grouped.values() for count in range(len(requests) + 1)}
    ordered_rates = sorted(rates)

    def required_cost(rate: Fraction) -> int:
        required_cost = 0
        for tenant, requests in grouped.items():
            count = (rate.numerator * len(requests) + rate.denominator - 1) // rate.denominator
            required_cost += prefix_costs[tenant][count]
        return required_cost

    lower = 0
    upper = len(ordered_rates) - 1
    best_index = 0
    while lower <= upper:
        middle = (lower + upper) // 2
        if required_cost(ordered_rates[middle]) <= budget:
            best_index = middle
            lower = middle + 1
        else:
            upper = middle - 1
    best_rate = ordered_rates[best_index]

    selected: list[int] = []
    completion_rates: dict[str, float] = {}
    for tenant, requests in grouped.items():
        count = (best_rate.numerator * len(requests) + best_rate.denominator - 1) // best_rate.denominator
        selected.extend(index for _, index in sorted_groups[tenant][:count])
        completion_rates[tenant] = count / len(requests)
    realized_cost = sum(int(costs[index]) for index in selected)
    return HindsightResult(
        benchmark="max_min_tenant_hindsight",
        selected_indices=tuple(sorted(selected)),
        admitted_count=len(selected),
        realized_cost=realized_cost,
        completion_rates=completion_rates,
    )
