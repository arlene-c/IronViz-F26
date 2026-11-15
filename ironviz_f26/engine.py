from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, fields, is_dataclass, replace
import math
from typing import Mapping, Sequence

from .ledger import Ledger
from .money import Money
from .pricing import PriceCatalog
from .state import ObservableState, PreAdmissionView
from .timeutil import utc_timestamp


@dataclass(frozen=True, slots=True)
class TraceEvent:
    run_id: str
    scenario_id: str
    seed: int
    timestamp: str
    request_id: str
    tenant: str
    original_model: str
    selected_model: str
    policy: str
    decision: str
    outcome: str
    estimated_cost: int
    reservation_before: int
    reservation_after_settlement: int
    realized_cost: int
    global_remaining: int
    tenant_remaining: int | None
    cumulative_counts: int
    is_counterfactual: bool = False
    observed_original_output_tokens: int | None = None
    modeled_routed_output_tokens: int | None = None
    overrun: int = 0
    cost_uncertainty_multiplier: float = 1.0
    source_request_id: str | None = None
    allowed_output_tokens: int = 0
    output_cap_exceeded: bool = False
    reservation_shortfall: bool = False
    denial_reason: str | None = None


class SimulationEngine:
    def __init__(
        self,
        catalog: PriceCatalog,
        policy,
        budget: int,
        estimator,
        *,
        strict_mode: bool = True,
        output_cap: int = 1024,
        output_caps: Mapping[str, int] | None = None,
        seed: int = 0,
        scenario_id: str = "scenario-0",
        tenant_roster: Sequence[str] = (),
        horizon_start: str | None = None,
        horizon_end: str | None = None,
    ):
        self.catalog = catalog
        self.policy = policy
        self.budget = int(budget)
        self.estimator = estimator
        self.strict_mode = strict_mode
        self.output_cap = int(output_cap)
        self.output_caps = {str(model): int(cap) for model, cap in (output_caps or {}).items()}
        if self.output_cap < 0 or any(cap < 0 for cap in self.output_caps.values()):
            raise ValueError("output caps must be non-negative")
        self.seed = int(seed)
        self.scenario_id = scenario_id
        self.tenant_roster = tuple(tenant_roster)
        self.horizon_start = utc_timestamp(horizon_start) if horizon_start else None
        self.horizon_end = utc_timestamp(horizon_end) if horizon_end else None
        if bool(self.horizon_start) != bool(self.horizon_end):
            raise ValueError("provide both horizon_start and horizon_end")
        if self.horizon_start and self.horizon_end <= self.horizon_start:
            raise ValueError("horizon_end must follow horizon_start")
        self.ledger = Ledger(self.budget)
        self.policy.reset({"budget": self.budget})
        self._events: list[TraceEvent] = []
        self._tenant_counts: dict[str, int] = defaultdict(int)

    def _observable_state(self) -> ObservableState:
        tenants = sorted(set(self.ledger._tenant_spent) | set(self.ledger._tenant_reserved) | set(self._tenant_counts))
        tenant_remaining = {tenant: self.ledger.tenant_remaining(tenant) for tenant in tenants}
        tenant_spent = {tenant: self.ledger.tenant_spent(tenant) for tenant in tenants}
        historical_spend = dict(tenant_spent)
        return ObservableState(
            global_remaining=self.ledger.global_remaining,
            tenant_remaining=tenant_remaining,
            tenant_spent=tenant_spent,
            historical_spend=historical_spend,
            counts=self._tenant_counts,
        )

    def _coerce_row(self, row: Mapping[str, object] | object) -> dict[str, object]:
        if isinstance(row, Mapping):
            return dict(row)
        if is_dataclass(row):
            return {field.name: getattr(row, field.name) for field in fields(row)}
        if hasattr(row, "__dict__"):
            return {k: getattr(row, k) for k in row.__dict__ if not k.startswith("_")}
        raise TypeError(f"Unsupported request row type: {type(row)!r}")

    def _pre_admission_view(
        self,
        row: Mapping[str, object],
        *,
        provider_override: str | None = None,
        model_override: str | None = None,
        estimate_multiplier: float = 1.0,
    ) -> PreAdmissionView:
        provider = provider_override or str(row["provider"])
        model = model_override or str(row["model"])
        record = self.catalog.lookup(provider, model)
        input_tokens = int(row["input_tokens"])
        cached_input_tokens = int(row.get("cached_input_tokens", 0))
        uncached_tokens = max(0, input_tokens - cached_input_tokens)
        input_cost = Money.cost_for_tokens(uncached_tokens, record.input_price) + Money.cost_for_tokens(
            cached_input_tokens,
            record.cached_input_price,
        )
        output_price = record.output_price
        try:
            est = self.estimator.estimate(model)
        except TypeError:
            est = self.estimator.estimate()
        return PreAdmissionView(
            request_id=str(row["request_id"]),
            timestamp=str(row["timestamp"]),
            tenant=str(row["tenant"]),
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            input_cost=input_cost,
            output_price=output_price,
            estimated_cost=max(input_cost, int(math.ceil(int(est) * estimate_multiplier))),
        )

    def run(
        self,
        requests: Sequence[Mapping[str, object] | object],
        *,
        cost_multipliers: Sequence[float] | None = None,
        estimated_costs: Mapping[tuple[str, str], int] | None = None,
    ) -> list[TraceEvent]:
        self.ledger = Ledger(self.budget)
        self._events = []
        self._tenant_counts = defaultdict(int)
        normalized = [self._coerce_row(row) for row in requests]
        for row in normalized:
            row["timestamp"] = utc_timestamp(str(row["timestamp"]))
            self.catalog.lookup(str(row["provider"]), str(row["model"]))
        if len({str(row["request_id"]) for row in normalized}) != len(normalized):
            raise ValueError("duplicate request_id")
        ordered = sorted(
            normalized,
            key=lambda row: (str(row["timestamp"]), str(row["request_id"])),
        )
        if cost_multipliers is None:
            ordered_cost_multipliers = [1.0] * len(ordered)
        else:
            if len(cost_multipliers) != len(ordered):
                raise ValueError("cost_multipliers must contain one value per request")
            ordered_cost_multipliers = [float(value) for value in cost_multipliers]
            if any(not math.isfinite(value) or value < 0 for value in ordered_cost_multipliers):
                raise ValueError("cost multipliers must be finite and non-negative")
        if estimated_costs is not None and any(int(value) < 0 for value in estimated_costs.values()):
            raise ValueError("estimated costs must be non-negative integer micro-USD values")
        policy_cfg = {
            "budget": self.budget,
            "tenants": self.tenant_roster,
            "start_timestamp": self.horizon_start,
            "end_timestamp": self.horizon_end,
        }
        self.policy.reset(policy_cfg)
        if self.horizon_start and any(not self.horizon_start <= str(row["timestamp"]) <= self.horizon_end for row in ordered):
            raise ValueError("request outside configured horizon")
        if hasattr(self.policy, "prepare_run"):
            self.policy.prepare_run(len(ordered), self.seed)

        for request_index, row in enumerate(ordered):
            cost_multiplier = ordered_cost_multipliers[request_index]
            original_view = self._pre_admission_view(row, estimate_multiplier=cost_multiplier)
            if estimated_costs is not None:
                original_estimate = estimated_costs.get((original_view.request_id, original_view.model))
                if original_estimate is not None:
                    original_view = replace(original_view, estimated_cost=int(original_estimate))
            state = self._observable_state()
            route = None
            if hasattr(self.policy, "route_for"):
                route = self.policy.route_for(request_index, original_view, state, self.catalog)
            view = (
                self._pre_admission_view(
                    row,
                    provider_override=route[0],
                    model_override=route[1],
                    estimate_multiplier=cost_multiplier,
                )
                if route is not None
                else original_view
            )
            if route is not None and estimated_costs is not None:
                routed_estimate = estimated_costs.get((view.request_id, view.model))
                if routed_estimate is not None:
                    view = replace(view, estimated_cost=int(routed_estimate))
            original_output_tokens = int(row.get("output_tokens", 0))
            modeled_routed_output_tokens = (
                max(0, int(math.floor(original_output_tokens * route[2] + 0.5))) if route is not None else None
            )
            output_tokens = modeled_routed_output_tokens if route is not None else original_output_tokens
            policy_label = getattr(self.policy, "label", self.policy.__class__.__name__)

            decision = bool(self.policy.decide(view, state))
            if self.strict_mode and view.input_cost > view.estimated_cost:
                decision = False
            if not decision:
                event = TraceEvent(
                    run_id=f"run-{self.seed}",
                    scenario_id=self.scenario_id,
                    seed=self.seed,
                    timestamp=view.timestamp,
                    request_id=view.request_id,
                    tenant=view.tenant,
                    original_model=original_view.model,
                    selected_model=view.model,
                    policy=policy_label,
                    decision="REJECTED",
                    outcome="REJECTED",
                    estimated_cost=view.estimated_cost,
                    reservation_before=0,
                    reservation_after_settlement=0,
                    realized_cost=0,
                    global_remaining=self.ledger.global_remaining,
                    tenant_remaining=self.ledger.tenant_remaining(view.tenant),
                    cumulative_counts=len(self._events),
                    is_counterfactual=route is not None,
                    observed_original_output_tokens=original_output_tokens,
                    modeled_routed_output_tokens=modeled_routed_output_tokens,
                    cost_uncertainty_multiplier=cost_multiplier,
                    source_request_id=str(row.get("source_request_id", row["request_id"])),
                    denial_reason=("INPUT_COST" if view.input_cost > view.estimated_cost else "GLOBAL_BUDGET" if view.estimated_cost > state.global_remaining else "POLICY"),
                )
                self._append_event(event)
                continue

            reservation_before = view.estimated_cost
            try:
                self.ledger.reserve(view.tenant, reservation_before, reservation_id=view.request_id)
            except ValueError:
                event = TraceEvent(
                    run_id=f"run-{self.seed}",
                    scenario_id=self.scenario_id,
                    seed=self.seed,
                    timestamp=view.timestamp,
                    request_id=view.request_id,
                    tenant=view.tenant,
                    original_model=original_view.model,
                    selected_model=view.model,
                    policy=policy_label,
                    decision="REJECTED",
                    outcome="REJECTED",
                    estimated_cost=view.estimated_cost,
                    reservation_before=reservation_before,
                    reservation_after_settlement=0,
                    realized_cost=0,
                    global_remaining=self.ledger.global_remaining,
                    tenant_remaining=self.ledger.tenant_remaining(view.tenant),
                    cumulative_counts=len(self._events),
                    is_counterfactual=route is not None,
                    observed_original_output_tokens=original_output_tokens,
                    modeled_routed_output_tokens=modeled_routed_output_tokens,
                    cost_uncertainty_multiplier=cost_multiplier,
                    source_request_id=str(row.get("source_request_id", row["request_id"])),
                    denial_reason="GLOBAL_BUDGET",
                )
                self._append_event(event)
                continue

            output_cap = self.output_caps.get(view.model, self.output_cap)
            max_allowed = min(
                output_cap,
                max(0, reservation_before - view.input_cost) * 1_000_000 // view.output_price
                if view.output_price > 0
                else output_cap,
            )
            if self.strict_mode:
                allowed = max(0, min(output_tokens, max_allowed))
                realized_cost = view.input_cost + Money.cost_for_tokens(allowed, view.output_price)
                outcome_base = "COMPLETED" if output_tokens <= max_allowed else "TRUNCATED"
            else:
                allowed = min(output_tokens, output_cap)
                realized_cost = view.input_cost + Money.cost_for_tokens(allowed, view.output_price)
                outcome_base = "COMPLETED" if output_tokens <= output_cap else "TRUNCATED"
            outcome_suffix = "ROUTED_CF" if route is not None else "ORIGINAL"
            outcome = f"{outcome_base}_{outcome_suffix}"

            settlement_delta = reservation_before - realized_cost
            self.ledger.settle(view.tenant, settlement_delta, reservation_id=view.request_id)
            event = TraceEvent(
                run_id=f"run-{self.seed}",
                scenario_id=self.scenario_id,
                seed=self.seed,
                timestamp=view.timestamp,
                request_id=view.request_id,
                tenant=view.tenant,
                original_model=original_view.model,
                selected_model=view.model,
                policy=policy_label,
                decision="ADMITTED",
                outcome=outcome,
                estimated_cost=view.estimated_cost,
                reservation_before=reservation_before,
                reservation_after_settlement=realized_cost,
                realized_cost=realized_cost,
                global_remaining=self.ledger.global_remaining,
                tenant_remaining=self.ledger.tenant_remaining(view.tenant),
                cumulative_counts=len(self._events) + 1,
                is_counterfactual=route is not None,
                observed_original_output_tokens=original_output_tokens,
                modeled_routed_output_tokens=modeled_routed_output_tokens,
                overrun=max(0, realized_cost - reservation_before),
                cost_uncertainty_multiplier=cost_multiplier,
                source_request_id=str(row.get("source_request_id", row["request_id"])),
                allowed_output_tokens=allowed,
                output_cap_exceeded=output_tokens > output_cap,
                reservation_shortfall=self.strict_mode and output_tokens > (
                    max(0, reservation_before - view.input_cost) * 1_000_000 // view.output_price
                    if view.output_price else output_tokens
                ),
            )
            self._append_event(event)

        return self._events

    def _append_event(self, event: TraceEvent) -> None:
        self._events.append(event)
        self._tenant_counts[event.tenant] += 1
        state = self._observable_state()
        self.policy.observe(event.outcome, state)
        balance = self.policy.entitlement_remaining(event.tenant, state) if hasattr(self.policy, "entitlement_remaining") else None
        self._events[-1] = replace(event, tenant_remaining=balance, cumulative_counts=len(self._events))
