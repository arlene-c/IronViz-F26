from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import math
from typing import Mapping

from .state import ObservableState, PreAdmissionView


class BasePolicy:
    def reset(self, cfg: dict | None = None) -> None:
        self.cfg = cfg or {}

    def decide(self, view: PreAdmissionView, state: ObservableState) -> bool:
        raise NotImplementedError

    def observe(self, outcome: str, state: ObservableState) -> None:
        return None


class FCFS(BasePolicy):
    """Admission iff the modeled reservation fits in the global remaining budget."""

    def decide(self, view: PreAdmissionView, state: ObservableState) -> bool:
        return state.global_remaining >= view.estimated_cost


@dataclass
class Quotas(BasePolicy):
    tenant_weights: Mapping[str, float] | None = None
    budget: int | None = None

    def __post_init__(self) -> None:
        self._weights = dict(self.tenant_weights or {})
        self.reset({"budget": self.budget})

    def reset(self, cfg: dict | None = None) -> None:
        self.cfg = cfg or {}
        budget_value = self.cfg.get("budget")
        if budget_value is None:
            budget_value = self.budget or 0
        self.budget = int(budget_value)
        self._weights = dict(self.tenant_weights or {})
        tenants = self.cfg.get("tenants", ())
        if not self._weights and tenants:
            self._weights = {tenant: 1.0 for tenant in tenants}
        if any(not math.isfinite(float(w)) or float(w) < 0 for w in self._weights.values()):
            raise ValueError("tenant weights must be finite and non-negative")
        if self._weights and sum(self._weights.values()) <= 0:
            raise ValueError("tenant weights must have a positive sum")

    def entitlement_remaining(self, tenant, state):
        if not self._weights:
            raise ValueError("equal quotas require a configured tenant roster")
        share = int(self.budget * self._weights.get(tenant, 0) / sum(self._weights.values()))
        return share - state.tenant_spent.get(tenant, 0)

    def decide(self, view: PreAdmissionView, state: ObservableState) -> bool:
        if state.global_remaining < view.estimated_cost:
            return False
        tenant_available = self.entitlement_remaining(view.tenant, state)
        return tenant_available >= view.estimated_cost


def _timestamp_seconds(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


class _TimedPolicy(BasePolicy):
    def reset(self, cfg: dict | None = None) -> None:
        super().reset(cfg)
        self.budget = int(self.cfg.get("budget", 0))
        self._start = _timestamp_seconds(self.cfg["start_timestamp"]) if self.cfg.get("start_timestamp") else None
        self._end = _timestamp_seconds(self.cfg["end_timestamp"]) if self.cfg.get("end_timestamp") else None
        self._horizon = max(0.0, self._end - self._start) if self._start is not None and self._end is not None else 0.0

    def progress(self, timestamp: str) -> float:
        if self._start is None or self._end is None:
            raise ValueError("timed policies require a configured start/end horizon")
        current = _timestamp_seconds(timestamp)
        start = self._start if self._start is not None else current
        horizon = self._horizon if self._horizon > 0 else 1.0
        return min(1.0, max(0.0, (current - start) / horizon))


class AdaptiveSharing(_TimedPolicy):
    """Quota protection with immediate loans capped by borrower protected share."""

    def __init__(
        self,
        tenant_weights: Mapping[str, float] | None = None,
        *,
        rho: float = 0.1,
        window: float = 3600.0,
        max_borrow_fraction: float = 0.5,
    ) -> None:
        if not 0 <= rho <= 1:
            raise ValueError("rho must be between 0 and 1")
        if window <= 0:
            raise ValueError("window must be positive")
        if not 0 <= max_borrow_fraction <= 1:
            raise ValueError("max_borrow_fraction must be between 0 and 1")
        self.tenant_weights = dict(tenant_weights or {})
        self.rho = float(rho)
        self.window = float(window)
        self.max_borrow_fraction = float(max_borrow_fraction)
        self.reset({})

    def reset(self, cfg: dict | None = None) -> None:
        super().reset(cfg)
        tenants = list(self.tenant_weights) or list(self.cfg.get("tenants", ()))
        weights = self.tenant_weights or {tenant: 1.0 for tenant in tenants}
        if any(not math.isfinite(float(weight)) or float(weight) < 0 for weight in weights.values()):
            raise ValueError("tenant weights must be finite and non-negative")
        weight_total = sum(float(weight) for weight in weights.values())
        if tenants and weight_total <= 0:
            raise ValueError("tenant weights must have a positive sum")
        self._weights = {tenant: float(weight) / weight_total for tenant, weight in weights.items()} if weight_total else {}
        self.protected = {tenant: self.budget * weight for tenant, weight in self._weights.items()}
        self.lender_debits: dict[str, float] = {tenant: 0.0 for tenant in self.protected}
        self.borrowed_spend: dict[str, float] = {tenant: 0.0 for tenant in self.protected}
        self.borrowed_reserved: dict[str, float] = {tenant: 0.0 for tenant in self.protected}
        self._spend_history: dict[str, deque[tuple[float, int]]] = {
            tenant: deque() for tenant in self.protected
        }
        self._spend_window_totals: dict[str, int] = {tenant: 0 for tenant in self.protected}
        self._pending: dict[str, tuple[str, float, list[tuple[str, float]], int]] = {}
        self._last_seen_spend: dict[str, int] = {tenant: 0 for tenant in self.protected}
        self._current_request: tuple[str, str, str] | None = None

    def _run_rate(self, tenant: str, now: float) -> float:
        history = self._spend_history.setdefault(tenant, deque())
        cutoff = now - self.window
        total = self._spend_window_totals.get(tenant, 0)
        while history and history[0][0] < cutoff:
            _, expired_cost = history.popleft()
            total -= expired_cost
        self._spend_window_totals[tenant] = max(0, total)
        return max(0, total) / self.window

    def entitlement_remaining(self, tenant, state):
        # Remaining protected own funds; borrowing capacity is not an entitlement.
        own_spend = state.tenant_spent.get(tenant, 0) - self.borrowed_spend.get(tenant, 0)
        return max(0, int(self.protected.get(tenant, 0) - own_spend - self.lender_debits.get(tenant, 0)))

    def _reserve(self, tenant: str, progress: float, now: float) -> float:
        protected = self.protected.get(tenant, 0.0)
        remaining_horizon = max(0.0, self._horizon * (1.0 - progress))
        rho_reserve = self.rho * protected * (1.0 - progress)
        rate_reserve = self._run_rate(tenant, now) * remaining_horizon
        return max(rho_reserve, rate_reserve)

    def decide(self, view: PreAdmissionView, state: ObservableState) -> bool:
        self._current_request = (view.tenant, view.timestamp, view.request_id)
        reservation = int(view.estimated_cost)
        if reservation < 0 or state.global_remaining < reservation:
            return False
        tenant = view.tenant
        protected = self.protected.get(tenant, 0.0)
        spent = int(state.tenant_spent.get(tenant, 0))
        own_available = max(0.0, protected - spent - self.lender_debits.get(tenant, 0.0))
        own_funding = min(float(reservation), own_available)
        loan_needed = float(reservation) - own_funding
        if loan_needed <= 0:
            self._pending[view.request_id] = (tenant, own_funding, [], spent)
            return True

        borrower_limit = max(
            0.0,
            protected * self.max_borrow_fraction
            - self.borrowed_spend.get(tenant, 0.0)
            - self.borrowed_reserved.get(tenant, 0.0),
        )
        if loan_needed > borrower_limit:
            return False

        now = _timestamp_seconds(view.timestamp)
        progress = self.progress(view.timestamp)
        lender_capacity: list[tuple[str, float]] = []
        for lender in sorted(self.protected):
            if lender == tenant:
                continue
            available = max(
                0.0,
                self.protected[lender]
                - int(state.tenant_spent.get(lender, 0))
                - self.lender_debits.get(lender, 0.0)
                - self._reserve(lender, progress, now),
            )
            if available:
                lender_capacity.append((lender, available))
        lender_capacity.sort(key=lambda item: (-item[1], item[0]))

        allocations: list[tuple[str, float]] = []
        remaining_loan = loan_needed
        for lender, available in lender_capacity:
            amount = min(available, remaining_loan)
            if amount:
                allocations.append((lender, amount))
                remaining_loan -= amount
            if remaining_loan <= 0:
                break
        if remaining_loan > 1e-9:
            return False

        for lender, amount in allocations:
            self.lender_debits[lender] = self.lender_debits.get(lender, 0.0) + amount
        self.borrowed_reserved[tenant] = self.borrowed_reserved.get(tenant, 0.0) + loan_needed
        self._pending[view.request_id] = (tenant, own_funding, allocations, spent)
        return True

    def observe(self, outcome: str, state: ObservableState) -> None:
        if self._current_request is None:
            return
        tenant, timestamp_text, request_id = self._current_request
        timestamp = _timestamp_seconds(timestamp_text)
        current_spend = int(state.tenant_spent.get(tenant, 0))
        spend_delta = max(0, current_spend - self._last_seen_spend.get(tenant, 0))
        pending = self._pending.pop(request_id, None)
        if pending is not None:
            pending_tenant, own_funding, allocations, spend_before = pending
            actual_spend = max(0, current_spend - spend_before)
            borrowed_used = 0.0 if outcome == "REJECTED" else max(0.0, actual_spend - own_funding)
            remaining_used = borrowed_used
            allocated_total = sum(allocated for _, allocated in allocations)
            self.borrowed_reserved[pending_tenant] = max(
                0.0,
                self.borrowed_reserved.get(pending_tenant, 0.0) - allocated_total,
            )
            for lender, allocated in allocations:
                used = min(allocated, remaining_used)
                self.lender_debits[lender] = max(0.0, self.lender_debits.get(lender, 0.0) - (allocated - used))
                remaining_used -= used
            self.borrowed_spend[pending_tenant] = self.borrowed_spend.get(pending_tenant, 0.0) + borrowed_used
        if spend_delta:
            self._spend_history.setdefault(tenant, deque()).append((timestamp, spend_delta))
            self._spend_window_totals[tenant] = self._spend_window_totals.get(tenant, 0) + spend_delta
        self._last_seen_spend[tenant] = current_spend
        self._current_request = None


class Pacing(_TimedPolicy):
    """Admission against a configured cumulative spending target curve."""

    def __init__(
        self,
        *,
        slack: float = 0.05,
        target_curve: tuple[tuple[float, float], ...] = ((0.0, 0.0), (1.0, 1.0)),
    ) -> None:
        if not 0 <= slack <= 1:
            raise ValueError("slack must be between 0 and 1")
        if not target_curve or target_curve[0][0] != 0 or target_curve[-1][0] != 1:
            raise ValueError("target_curve must start at 0 and end at 1")
        if any(
            not 0 <= time_fraction <= 1
            or not 0 <= spend_fraction <= 1
            or (index and (time_fraction <= target_curve[index - 1][0] or spend_fraction < target_curve[index - 1][1]))
            for index, (time_fraction, spend_fraction) in enumerate(target_curve)
        ):
            raise ValueError("target_curve must be monotone and normalized")
        self.slack = float(slack)
        self.target_curve = tuple(target_curve)
        self.reset({})

    def _target(self, progress: float) -> float:
        for index in range(1, len(self.target_curve)):
            left_time, left_spend = self.target_curve[index - 1]
            right_time, right_spend = self.target_curve[index]
            if progress <= right_time:
                ratio = (progress - left_time) / (right_time - left_time)
                return left_spend + ratio * (right_spend - left_spend)
        return self.target_curve[-1][1]

    def decide(self, view: PreAdmissionView, state: ObservableState) -> bool:
        reservation = int(view.estimated_cost)
        if reservation < 0 or reservation > state.global_remaining:
            return False
        cumulative_spend = self.budget - state.global_remaining
        cumulative_allowance = self.budget * min(1.0, self._target(self.progress(view.timestamp)) + self.slack)
        return cumulative_spend + reservation <= cumulative_allowance


class CostThreshold(BasePolicy):
    """Simple reservation threshold tuned only from an explicit training sample."""

    def __init__(self, tau: int | None = None) -> None:
        self.tau = int(tau) if tau is not None else None
        self.training_budget: int | None = None
        self.reset({})

    def fit(
        self,
        training_reservations: list[int] | tuple[int, ...],
        budget: int,
        *,
        candidate_count: int = 64,
        settlement_costs: list[int] | None = None,
        completion_flags: list[bool] | None = None,
    ) -> "CostThreshold":
        costs = [int(cost) for cost in training_reservations]
        settlements = list(settlement_costs) if settlement_costs is not None else costs
        completions = list(completion_flags) if completion_flags is not None else [True] * len(costs)
        if len(settlements) != len(costs) or len(completions) != len(costs) or any(v < 0 for v in settlements):
            raise ValueError("training settlement/completion vectors must match reservations")
        if not costs:
            raise ValueError("training_reservations must not be empty")
        if any(cost < 0 for cost in costs) or budget < 0:
            raise ValueError("training costs and budget must be non-negative")
        if candidate_count < 2:
            raise ValueError("candidate_count must be at least two")

        unique_costs = sorted(set(costs))
        if len(unique_costs) > candidate_count:
            positions = {
                round(index * (len(unique_costs) - 1) / (candidate_count - 1))
                for index in range(candidate_count)
            }
            candidates = [unique_costs[position] for position in sorted(positions)]
        else:
            candidates = unique_costs
        self.tuning_candidates = tuple(candidates)
        best_key: tuple[int, int, int] | None = None
        best_tau: int | None = None
        for tau in candidates:
            count = 0
            spend = 0
            for cost, actual, complete in zip(costs, settlements, completions):
                if cost <= tau and spend + cost <= budget:
                    count += int(complete)
                    spend += actual
            key = (count, -spend, -tau)
            if best_key is None or key > best_key:
                best_key = key
                best_tau = tau
        self.tau = best_tau
        self.training_budget = int(budget)
        return self

    def decide(self, view: PreAdmissionView, state: ObservableState) -> bool:
        if self.tau is None:
            raise RuntimeError("CostThreshold must be initialized with tau or fit on training data")
        return view.estimated_cost <= self.tau and view.estimated_cost <= state.global_remaining
