from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from itertools import product
import json
import math
import time
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .benchmarks import max_count_hindsight, max_min_tenant_hindsight
from .engine import SimulationEngine, TraceEvent
from .estimators import GlobalEstimator
from .money import Money
from .policies import AdaptiveSharing, CostThreshold, FCFS, Pacing, Quotas
from .pricing import PriceCatalog
from .routing import RoutingWrapper

DEFAULT_POLICIES = (
    "FCFS",
    "Quotas",
    "TrainingQuotas",
    "Adaptive",
    "Pacing",
    "Threshold",
    "FCFS+Routing",
    "Adaptive+Routing",
)


@dataclass(frozen=True)
class ExperimentConfig:
    budget_fractions: tuple[float, ...] = (0.5, 0.7, 0.85, 1.0)
    replicates: int = 3
    seed: int = 2026
    training_fraction: float = 0.2
    bootstrap: bool = True
    bootstrap_method: str = "day_block"
    bootstrap_window_days: float = 3.0
    bootstrap_block_hours: int = 12
    demand_imbalance: tuple[float, ...] = (1.0, 1.5)
    estimator_noise: tuple[float, ...] = (0.0,)
    routing_eligibility: tuple[float, ...] = (0.0, 0.5, 1.0)
    reservation_multipliers: tuple[float, ...] = (1.0,)
    routed_output_multipliers: tuple[float, ...] = (0.7,)
    routing_sigma: float = 0.0
    policies: tuple[str, ...] = DEFAULT_POLICIES
    trace_replicates: tuple[int, ...] = (0, 1)
    trace_policies: tuple[str, ...] | None = None
    timeseries_stride: int = 1
    strict_mode: bool = True
    output_cap: int = 1024
    model_output_caps: Mapping[str, int] = field(default_factory=dict)
    routing_compatibility: tuple[tuple[str, str, str, str], ...] = ()
    reservation_mode: str = "mean"
    reservation_quantile: float = 0.9
    data_label: str = "USER-PROVIDED CLEANED INPUT"

    def __post_init__(self) -> None:
        if self.replicates < 1:
            raise ValueError("replicates must be at least one")
        if self.bootstrap_method not in {"day_block", "local_12h"}:
            raise ValueError("bootstrap_method must be day_block or local_12h")
        if self.bootstrap_window_days < 0 or self.bootstrap_block_hours <= 0:
            raise ValueError("bootstrap window must be non-negative and block hours positive")
        if not 0 < self.training_fraction < 1:
            raise ValueError("training_fraction must be between 0 and 1")
        if any(not 0 <= fraction <= 1 for fraction in self.budget_fractions):
            raise ValueError("budget fractions must be between 0 and 1")
        if any(value < 0 for value in self.demand_imbalance):
            raise ValueError("demand imbalance factors must be non-negative")
        if any(value < 0 for value in self.estimator_noise):
            raise ValueError("estimator noise values must be non-negative")
        if any(value < 0 for value in self.reservation_multipliers):
            raise ValueError("reservation multipliers must be non-negative")
        if any(not 0 <= value <= 1 for value in self.routing_eligibility):
            raise ValueError("routing eligibility values must be between 0 and 1")
        if any(value <= 0 for value in self.routed_output_multipliers):
            raise ValueError("routed output multipliers must be positive")
        if self.routing_sigma < 0 or self.timeseries_stride < 1:
            raise ValueError("routing_sigma must be non-negative and timeseries_stride positive")
        if self.reservation_mode not in {"mean", "quantile", "cap"}:
            raise ValueError("reservation_mode must be mean, quantile, or cap")
        if not 0 <= self.reservation_quantile <= 1:
            raise ValueError("reservation_quantile must be between 0 and 1")
        if self.output_cap < 0 or any(int(cap) < 0 for cap in self.model_output_caps.values()):
            raise ValueError("model output caps must be non-negative")
        unknown = set(self.policies) - set(DEFAULT_POLICIES)
        if unknown:
            raise ValueError(f"unknown policies: {', '.join(sorted(unknown))}")
        if self.trace_policies is not None:
            unknown_traces = set(self.trace_policies) - set(DEFAULT_POLICIES)
            if unknown_traces:
                raise ValueError(f"unknown trace policies: {', '.join(sorted(unknown_traces))}")


@dataclass
class ExperimentResults:
    run_metrics: pd.DataFrame
    tenant_metrics: pd.DataFrame
    experiment_summary: pd.DataFrame
    policy_comparisons: pd.DataFrame
    regime_map: pd.DataFrame
    budget_timeseries: pd.DataFrame
    event_traces: pd.DataFrame
    scenario_metadata: dict[str, Any]


def _as_dict(row: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    return {name: getattr(row, name) for name in row.__dataclass_fields__}


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def modeled_request_cost(row: Mapping[str, Any], catalog: PriceCatalog) -> int:
    price = catalog.lookup(str(row["provider"]), str(row["model"]))
    input_tokens = int(row["input_tokens"])
    cached_tokens = int(row.get("cached_input_tokens", 0))
    output_tokens = int(row["output_tokens"])
    return (
        Money.cost_for_tokens(input_tokens - cached_tokens, price.input_price)
        + Money.cost_for_tokens(cached_tokens, price.cached_input_price)
        + Money.cost_for_tokens(output_tokens, price.output_price)
    )


def _seed_value(seed: int, *spawn_key: int) -> int:
    sequence = np.random.SeedSequence(int(seed), spawn_key=tuple(int(value) for value in spawn_key))
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


def day_block_bootstrap(rows: Sequence[Mapping[str, Any]], seed: int, replicate: int) -> list[dict[str, Any]]:
    """Resample complete UTC calendar days, retaining within-day row structure."""
    groups: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        normalized = dict(row)
        groups[_parse_timestamp(str(row["timestamp"])).date()].append(normalized)
    if not groups:
        return []

    days = sorted(groups)
    rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(0, int(replicate))))
    selected_days = rng.choice(len(days), size=len(days), replace=True)
    sampled: list[dict[str, Any]] = []
    for draw_index, day_index in enumerate(selected_days):
        day = days[int(day_index)]
        shift = draw_index - (day - days[0]).days
        for row_index, row in enumerate(groups[day]):
            copied = dict(row)
            original_id = str(row["request_id"])
            copied["source_request_id"] = str(row.get("source_request_id", original_id))
            copied["request_id"] = f"{original_id}__boot{replicate}_{draw_index}_{row_index}"
            shifted = _parse_timestamp(str(row["timestamp"])) + timedelta(days=shift)
            copied["timestamp"] = shifted.isoformat().replace("+00:00", "Z")
            sampled.append(copied)
    return sorted(sampled, key=lambda row: (str(row["timestamp"]), str(row["request_id"])))


def local_block_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    seed: int,
    replicate: int,
    *,
    block_hours: int = 12,
    window_days: float = 3.0,
) -> list[dict[str, Any]]:
    """Retiming of source blocks sampled within +/- window_days of each target block."""
    if block_hours <= 0 or window_days < 0:
        raise ValueError("block_hours must be positive and window_days non-negative")
    if not rows:
        return []
    block = timedelta(hours=block_hours)
    parsed = [_parse_timestamp(str(row["timestamp"])) for row in rows]
    timeline_start = min(parsed).replace(hour=0, minute=0, second=0, microsecond=0)
    block_seconds = block.total_seconds()
    last_offset = max((timestamp - timeline_start).total_seconds() for timestamp in parsed)
    block_count = int(last_offset // block_seconds) + 1
    blocks: list[list[tuple[Mapping[str, Any], datetime]]] = [[] for _ in range(block_count)]
    for row, timestamp in zip(rows, parsed):
        block_index = min(block_count - 1, int((timestamp - timeline_start).total_seconds() // block_seconds))
        blocks[block_index].append((row, timestamp))

    window_blocks = int(round(window_days * 24 / block_hours))
    rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(0, int(replicate), 12)))
    sampled: list[dict[str, Any]] = []
    for target_block in range(block_count):
        low = max(0, target_block - window_blocks)
        high = min(block_count - 1, target_block + window_blocks)
        source_block = int(rng.integers(low, high + 1))
        source_start = timeline_start + source_block * block
        target_start = timeline_start + target_block * block
        for row_index, (row, timestamp) in enumerate(blocks[source_block]):
            copied = dict(row)
            source_id = str(row.get("source_request_id", row["request_id"]))
            copied["source_request_id"] = source_id
            copied["request_id"] = f"{source_id}__local{block_hours}h{replicate}_{target_block}_{row_index}"
            copied["timestamp"] = (target_start + (timestamp - source_start)).isoformat().replace("+00:00", "Z")
            sampled.append(copied)
    return sorted(sampled, key=lambda row: (str(row["timestamp"]), str(row["request_id"])))


def _volume_reweight(
    rows: Sequence[Mapping[str, Any]],
    factor: float,
    seed: int,
    replicate: int,
    imbalance_index: int,
) -> list[dict[str, Any]]:
    if factor == 1.0 or not rows:
        return [dict(row) for row in rows]
    counts = Counter(str(row["tenant"]) for row in rows)
    heavy_tenant = sorted(counts, key=lambda tenant: (-counts[tenant], tenant))[0]
    weights = np.asarray([factor if str(row["tenant"]) == heavy_tenant else 1.0 for row in rows], dtype=float)
    weights /= weights.sum()
    rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(3, replicate, imbalance_index)))
    selected = rng.choice(len(rows), size=len(rows), replace=True, p=weights)
    sampled: list[dict[str, Any]] = []
    for index, source_index in enumerate(selected):
        row = dict(rows[int(source_index)])
        source_id = str(row.get("source_request_id", row["request_id"]))
        row["source_request_id"] = source_id
        row["request_id"] = f"{source_id}__weight{imbalance_index}_{index}"
        sampled.append(row)
    return sorted(sampled, key=lambda row: (str(row["timestamp"]), str(row["request_id"])))


def _eligible_split(
    rows: Sequence[Mapping[str, Any]], training_fraction: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    normalized = sorted((_as_dict(row) for row in rows), key=lambda row: (str(row["timestamp"]), str(row["request_id"])))
    eligible = [
        row for row in normalized
        if str(row.get("original_status", "")).lower() == "success"
        and int(row.get("input_tokens", -1)) >= 0
        and int(row.get("output_tokens", -1)) >= 0
        and 0 <= int(row.get("cached_input_tokens", 0)) <= int(row.get("input_tokens", -1))
    ]
    excluded = len(normalized) - len(eligible)
    if len(eligible) < 2:
        raise ValueError("at least two eligible successful requests are required for train/test evaluation")
    train_count = min(len(eligible) - 1, max(1, int(len(eligible) * training_fraction)))
    return eligible[:train_count], eligible[train_count:], excluded


def _metrics(
    events: Sequence[TraceEvent],
    workload: Sequence[Mapping[str, Any]],
    catalog: PriceCatalog,
    *,
    budget: int,
    reference_cost: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    by_id = {str(row["request_id"]): row for row in workload}
    tenants = sorted({str(row["tenant"]) for row in workload})
    demand = Counter(str(row["tenant"]) for row in workload)
    reference_by_tenant: Counter[str] = Counter()
    demand_tokens: Counter[str] = Counter()
    for row in workload:
        tenant = str(row["tenant"])
        reference_by_tenant[tenant] += modeled_request_cost(row, catalog)
        demand_tokens[tenant] += int(row["input_tokens"]) + int(row["output_tokens"])

    completed_original_by_tenant: Counter[str] = Counter()
    completed_routed_by_tenant: Counter[str] = Counter()
    admitted_by_tenant: Counter[str] = Counter()
    rejected_by_tenant: Counter[str] = Counter()
    truncated_by_tenant: Counter[str] = Counter()
    realized_by_tenant: Counter[str] = Counter()
    served_tokens_by_tenant: Counter[str] = Counter()
    total_reference = sum(reference_by_tenant.values())
    total_demand_tokens = sum(demand_tokens.values())
    quartile_cuts = np.quantile(
        [int(row["input_tokens"]) + int(row["output_tokens"]) for row in workload],
        [0.25, 0.5, 0.75],
    )
    quartile_demand = [0, 0, 0, 0]
    quartile_completed = [0, 0, 0, 0]

    for row in workload:
        size = int(row["input_tokens"]) + int(row["output_tokens"])
        quartile = min(3, int(np.searchsorted(quartile_cuts, size, side="left")))
        quartile_demand[quartile] += 1
    for event in events:
        tenant = event.tenant
        row = by_id[event.request_id]
        if event.decision == "ADMITTED":
            admitted_by_tenant[tenant] += 1
            served_tokens_by_tenant[tenant] += int(row["input_tokens"]) + event.allowed_output_tokens
        if event.outcome == "COMPLETED_ORIGINAL":
            completed_original_by_tenant[tenant] += 1
        elif event.outcome == "COMPLETED_ROUTED_CF":
            completed_routed_by_tenant[tenant] += 1
        elif event.outcome == "REJECTED":
            rejected_by_tenant[tenant] += 1
        elif event.outcome.startswith("TRUNCATED"):
            truncated_by_tenant[tenant] += 1
        realized_by_tenant[tenant] += event.realized_cost
        size = int(row["input_tokens"]) + int(row["output_tokens"])
        quartile = min(3, int(np.searchsorted(quartile_cuts, size, side="left")))
        if event.outcome in {"COMPLETED_ORIGINAL", "COMPLETED_ROUTED_CF"}:
            quartile_completed[quartile] += 1

    admitted = sum(event.decision == "ADMITTED" for event in events)
    completed_original = sum(completed_original_by_tenant.values())
    completed_routed = sum(completed_routed_by_tenant.values())
    completed_total = completed_original + completed_routed
    rejected = sum(rejected_by_tenant.values())
    truncated = sum(truncated_by_tenant.values())
    realized_cost = sum(event.realized_cost for event in events)
    reserved_cost = sum(event.reservation_before for event in events if event.decision == "ADMITTED")
    unused_reservation = max(0, reserved_cost - realized_cost)
    overrun = sum(event.overrun for event in events)
    completion_rates = [
        (completed_original_by_tenant[tenant] + completed_routed_by_tenant[tenant]) / demand[tenant]
        for tenant in tenants
    ]
    rate_sum = sum(completion_rates)
    rate_square_sum = sum(rate * rate for rate in completion_rates)
    jain = rate_sum * rate_sum / (len(completion_rates) * rate_square_sum) if rate_square_sum else 0.0
    mean_rate = rate_sum / len(completion_rates) if completion_rates else 0.0
    gini = (
        sum(abs(left - right) for left in completion_rates for right in completion_rates)
        / (2 * len(completion_rates) ** 2 * mean_rate)
        if mean_rate and completion_rates
        else 0.0
    )
    first_timestamp = _parse_timestamp(str(workload[0]["timestamp"])) if workload else None
    exhausted = next(
        (
            event
            for event in events
            if event.outcome == "REJECTED" and event.estimated_cost > event.global_remaining
        ),
        None,
    )
    time_to_exhaustion = (
        (_parse_timestamp(exhausted.timestamp) - first_timestamp).total_seconds()
        if exhausted and first_timestamp
        else None
    )
    metrics = {
        "request_count": len(workload),
        "admitted": admitted,
        "completed_original": completed_original,
        "completed_routed": completed_routed,
        "completed_total": completed_total,
        "rejected": rejected,
        "truncated": truncated,
        "admission_rate": admitted / len(workload) if workload else 0.0,
        "completion_rate_original": completed_original / len(workload) if workload else 0.0,
        "completion_rate_routed": completed_routed / len(workload) if workload else 0.0,
        "completion_rate_total": completed_total / len(workload) if workload else 0.0,
        "realized_cost_micro_usd": realized_cost,
        "reserved_micro_usd": reserved_cost,
        "unused_reservation_micro_usd": unused_reservation,
        "overrun_micro_usd": overrun,
        "cost_per_completed_request_micro_usd": realized_cost / completed_total if completed_total else None,
        "cost_per_original_completion_micro_usd": realized_cost / completed_original if completed_original else None,
        "cost_per_routed_completion_micro_usd": realized_cost / completed_routed if completed_routed else None,
        "budget_utilization": realized_cost / budget if budget else 0.0,
        "budget_remaining_micro_usd": budget - realized_cost,
        "budget_remaining_fraction": (budget - realized_cost) / budget if budget else 0.0,
        "time_to_budget_exhaustion_seconds": time_to_exhaustion,
        "min_tenant_completion_rate": min(completion_rates, default=0.0),
        "max_min_completion_gap": max(completion_rates, default=0.0) - min(completion_rates, default=0.0),
        "jain_completion_rate": jain,
        "gini_completion_rate": gini,
        "token_weighted_served_share": sum(served_tokens_by_tenant.values()) / total_demand_tokens if total_demand_tokens else 0.0,
        "cost_weighted_served_share": realized_cost / total_reference if total_reference else 0.0,
        "reference_cost_micro_usd": reference_cost,
        "completion_size_q1": quartile_completed[0] / quartile_demand[0] if quartile_demand[0] else 0.0,
        "completion_size_q2": quartile_completed[1] / quartile_demand[1] if quartile_demand[1] else 0.0,
        "completion_size_q3": quartile_completed[2] / quartile_demand[2] if quartile_demand[2] else 0.0,
        "completion_size_q4": quartile_completed[3] / quartile_demand[3] if quartile_demand[3] else 0.0,
    }
    tenant_rows: list[dict[str, Any]] = []
    for tenant in tenants:
        tenant_completed = completed_original_by_tenant[tenant] + completed_routed_by_tenant[tenant]
        tenant_reference = reference_by_tenant[tenant]
        tenant_rows.append(
            {
                "tenant": tenant,
                "demand_requests": demand[tenant],
                "admitted": admitted_by_tenant[tenant],
                "completed_original": completed_original_by_tenant[tenant],
                "completed_routed": completed_routed_by_tenant[tenant],
                "completed_total": tenant_completed,
                "rejected": rejected_by_tenant[tenant],
                "truncated": truncated_by_tenant[tenant],
                "admission_rate": admitted_by_tenant[tenant] / demand[tenant],
                "completion_rate_original": completed_original_by_tenant[tenant] / demand[tenant],
                "completion_rate_routed": completed_routed_by_tenant[tenant] / demand[tenant],
                "completion_rate_total": tenant_completed / demand[tenant],
                "realized_cost_micro_usd": realized_by_tenant[tenant],
                "reference_cost_micro_usd": tenant_reference,
                "spend_share": realized_by_tenant[tenant] / realized_cost if realized_cost else 0.0,
                "demand_share": demand[tenant] / len(workload) if workload else 0.0,
                "token_weighted_served_share": served_tokens_by_tenant[tenant] / demand_tokens[tenant]
                if demand_tokens[tenant]
                else 0.0,
                "cost_weighted_served_share": realized_by_tenant[tenant] / tenant_reference
                if tenant_reference
                else 0.0,
            }
        )
    return metrics, tenant_rows


class ExperimentRunner:
    def __init__(self, catalog: PriceCatalog, config: ExperimentConfig | None = None):
        self.catalog = catalog
        self.config = config or ExperimentConfig()

    def _compatibility_map(self) -> dict[tuple[str, str], tuple[str, str]]:
        if self.config.routing_compatibility:
            explicit = {
                (source_provider, source_model): (target_provider, target_model)
                for source_provider, source_model, target_provider, target_model in self.config.routing_compatibility
            }
            return explicit
        available = set(self.catalog._rows)
        candidates = {
            ("openai", "gpt-4o"): ("openai", "gpt-4o-mini"),
            ("anthropic", "claude-3.5-sonnet"): ("openai", "gpt-4o-mini"),
        }
        return {source: target for source, target in candidates.items() if source in available and target in available}

    def _policies(
        self,
        names: Sequence[str],
        *,
        training_costs: Sequence[int],
        training_tenant_weights: Mapping[str, float],
        training_reference: int,
        budget: int,
        fraction: float,
        eligibility: float,
        output_multiplier: float,
        sigma: float,
    ) -> dict[str, Any]:
        threshold = (
            CostThreshold().fit(training_costs, max(0, int(training_reference * fraction)))
            if "Threshold" in names
            else None
        )
        compatibility = self._compatibility_map()
        factories: dict[str, Any] = {
            "FCFS": FCFS,
            "Quotas": Quotas,
            "TrainingQuotas": lambda: Quotas(tenant_weights=training_tenant_weights),
            "Adaptive": AdaptiveSharing,
            "Pacing": Pacing,
            "Threshold": lambda: threshold,
            "FCFS+Routing": lambda: RoutingWrapper(
                FCFS(),
                compatibility_map=compatibility,
                eligibility_probability=eligibility,
                mu_pair=math.log(output_multiplier),
                sigma_pair=sigma,
            ),
            "Adaptive+Routing": lambda: RoutingWrapper(
                AdaptiveSharing(),
                compatibility_map=compatibility,
                eligibility_probability=eligibility,
                mu_pair=math.log(output_multiplier),
                sigma_pair=sigma,
            ),
        }
        policies = {name: factories[name]() for name in names}
        for name, policy in policies.items():
            policy.label = name
        return policies

    def run(self, requests: Sequence[Mapping[str, Any] | object]) -> ExperimentResults:
        experiment_started = time.perf_counter()
        training, evaluation, excluded = _eligible_split(requests, self.config.training_fraction)
        training_costs = [modeled_request_cost(row, self.catalog) for row in training]
        training_outputs_by_model: dict[str, list[int]] = defaultdict(list)
        for row in training:
            training_outputs_by_model[str(row["model"])].append(int(row["output_tokens"]))
        all_training_outputs = [int(row["output_tokens"]) for row in training]
        global_output_mean = float(np.mean(all_training_outputs))
        global_output_quantile = float(np.quantile(all_training_outputs, self.config.reservation_quantile))
        model_output_means = {
            model: float(np.mean(observations)) for model, observations in training_outputs_by_model.items()
        }
        model_output_quantiles = {
            model: float(np.quantile(observations, self.config.reservation_quantile))
            for model, observations in training_outputs_by_model.items()
        }

        def estimated_output_tokens(model: str) -> float:
            if config.reservation_mode == "cap":
                return float(config.model_output_caps.get(model, config.output_cap))
            if config.reservation_mode == "quantile":
                return model_output_quantiles.get(model, global_output_quantile)
            return model_output_means.get(model, global_output_mean)

        training_reference = sum(training_costs)
        training_spend_by_tenant: Counter[str] = Counter()
        for row, cost in zip(training, training_costs):
            training_spend_by_tenant[str(row["tenant"])] += cost
        training_tenant_total = sum(training_spend_by_tenant.values())
        training_tenant_weights = {
            tenant: cost / training_tenant_total for tenant, cost in training_spend_by_tenant.items()
        } if training_tenant_total else {}
        base_estimator = GlobalEstimator(training_costs)
        run_rows: list[dict[str, Any]] = []
        tenant_rows: list[dict[str, Any]] = []
        traces: list[dict[str, Any]] = []
        timeseries: list[dict[str, Any]] = []
        scenario_metadata: list[dict[str, Any]] = []
        config = self.config

        combination_indices = product(
            range(len(config.demand_imbalance)),
            range(len(config.estimator_noise)),
            range(len(config.reservation_multipliers)),
            range(len(config.routing_eligibility)),
            range(len(config.routed_output_multipliers)),
        )
        combinations = list(combination_indices)
        for imbalance_index, noise_index, reservation_index, eligibility_index, output_index in combinations:
            imbalance = config.demand_imbalance[imbalance_index]
            noise = config.estimator_noise[noise_index]
            reservation_multiplier = config.reservation_multipliers[reservation_index]
            eligibility = config.routing_eligibility[eligibility_index]
            output_multiplier = config.routed_output_multipliers[output_index]
            for replicate in range(config.replicates):
                if replicate == 0 or not config.bootstrap:
                    sampled = [dict(row) for row in evaluation]
                    workload_kind = "replay" if imbalance == 1.0 else "volume_reweighted_replay"
                else:
                    sample_seed = _seed_value(config.seed, 0, replicate, imbalance_index)
                    if config.bootstrap_method == "local_12h":
                        sampled = local_block_bootstrap(
                            evaluation,
                            sample_seed,
                            replicate,
                            block_hours=config.bootstrap_block_hours,
                            window_days=config.bootstrap_window_days,
                        )
                        workload_kind = "local_12h_block_bootstrap"
                    else:
                        sampled = day_block_bootstrap(evaluation, sample_seed, replicate)
                        workload_kind = "day_block_bootstrap"
                sampled = _volume_reweight(
                    sampled,
                    imbalance,
                    config.seed,
                    replicate,
                    imbalance_index,
                )
                sampled = sorted(sampled, key=lambda row: (str(row["timestamp"]), str(row["request_id"])))
                cost_seed = _seed_value(config.seed, 1, replicate, imbalance_index)
                cost_rng = np.random.default_rng(np.random.SeedSequence(cost_seed, spawn_key=(1,)))
                cost_draws = cost_rng.lognormal(-0.5 * noise * noise, noise, len(sampled))
                compatibility_map = self._compatibility_map()
                estimated_costs: dict[tuple[str, str], int] = {}
                for request_index, row in enumerate(sampled):
                    provider = str(row["provider"])
                    original_model = str(row["model"])
                    pairs = [(provider, original_model)]
                    routed_pair = compatibility_map.get((provider, original_model))
                    if routed_pair is not None:
                        pairs.append(routed_pair)
                    predicted_output = estimated_output_tokens(original_model)
                    for selected_provider, selected_model in pairs:
                        record = self.catalog.lookup(selected_provider, selected_model)
                        model_cap = int(config.model_output_caps.get(selected_model, config.output_cap))
                        route_length_factor = output_multiplier if selected_model != original_model else 1.0
                        estimated_tokens = predicted_output * float(cost_draws[request_index])
                        estimated_tokens *= reservation_multiplier * route_length_factor
                        reserved_tokens = min(model_cap, max(0, int(math.ceil(estimated_tokens))))
                        input_tokens = int(row["input_tokens"])
                        cached_tokens = int(row.get("cached_input_tokens", 0))
                        input_cost = Money.cost_for_tokens(input_tokens - cached_tokens, record.input_price)
                        input_cost += Money.cost_for_tokens(cached_tokens, record.cached_input_price)
                        estimated_costs[(str(row["request_id"]), selected_model)] = input_cost + Money.cost_for_tokens(
                            reserved_tokens,
                            record.output_price,
                        )
                scenario_seed = _seed_value(config.seed, 4, replicate, imbalance_index)
                scenario_id = (
                    f"i{imbalance:.2f}-n{noise:.2f}-r{reservation_multiplier:.2f}-rm{config.reservation_mode}"
                    f"-q{config.reservation_quantile:.2f}"
                    f"-e{eligibility:.2f}-m{output_multiplier:.2f}-rep{replicate:03d}"
                )
                reference_cost = sum(modeled_request_cost(row, self.catalog) for row in sampled)
                demand_counts = Counter(str(row["tenant"]) for row in sampled)
                imbalance_ratio = max(demand_counts.values(), default=0) / min(demand_counts.values()) if demand_counts else 0
                scenario_metadata.append(
                    {
                        "scenario_id": scenario_id,
                        "replicate": replicate,
                        "workload_kind": workload_kind,
                        "seed": scenario_seed,
                        "request_count": len(sampled),
                        "reference_cost_micro_usd": reference_cost,
                        "demand_imbalance_factor": imbalance,
                        "observed_tenant_volume_ratio": imbalance_ratio,
                        "estimator_noise_sigma": noise,
                        "reservation_multiplier": reservation_multiplier,
                        "reservation_mode": config.reservation_mode,
                        "reservation_quantile": config.reservation_quantile,
                        "model_output_caps": dict(config.model_output_caps),
                        "routing_eligibility_probability": eligibility,
                        "routed_output_length_multiplier": output_multiplier,
                        "trace": replicate in config.trace_replicates
                        and (config.trace_policies is None or bool(config.trace_policies)),
                        "trace_policies": list(config.trace_policies) if config.trace_policies is not None else list(config.policies),
                    }
                )
                for fraction in config.budget_fractions:
                    budget = int(reference_cost * fraction)
                    policies = self._policies(
                        config.policies,
                        training_costs=training_costs,
                        training_tenant_weights=training_tenant_weights,
                        training_reference=training_reference,
                        budget=budget,
                        fraction=fraction,
                        eligibility=eligibility,
                        output_multiplier=output_multiplier,
                        sigma=config.routing_sigma,
                    )
                    benchmark_max = max_count_hindsight(
                        [modeled_request_cost(row, self.catalog) for row in sampled], budget
                    )
                    benchmark_min = max_min_tenant_hindsight(
                        [str(row["tenant"]) for row in sampled],
                        [modeled_request_cost(row, self.catalog) for row in sampled],
                        budget,
                    )
                    scenario_key = f"{scenario_id}-budget{fraction:.2f}"
                    for policy_name, policy in policies.items():
                        policy_started = time.perf_counter()
                        engine = SimulationEngine(
                            catalog=self.catalog,
                            policy=policy,
                            budget=budget,
                            estimator=base_estimator,
                            strict_mode=config.strict_mode,
                            output_cap=config.output_cap,
                            output_caps=config.model_output_caps,
                            seed=scenario_seed,
                            scenario_id=scenario_key,
                        )
                        multipliers = [float(draw) * reservation_multiplier for draw in cost_draws]
                        events = engine.run(sampled, cost_multipliers=multipliers, estimated_costs=estimated_costs)
                        runtime_seconds = time.perf_counter() - policy_started
                        metrics, run_tenants = _metrics(
                            events,
                            sampled,
                            self.catalog,
                            budget=budget,
                            reference_cost=reference_cost,
                        )
                        run_id = f"{scenario_key}-{policy_name}-rep{replicate:03d}"
                        run_metadata = {
                            "run_id": run_id,
                            "scenario_id": scenario_key,
                            "seed": scenario_seed,
                            "policy": policy_name,
                            "budget_fraction": fraction,
                            "budget_micro_usd": budget,
                            "replicate": replicate,
                            "workload_kind": workload_kind,
                            "demand_imbalance": imbalance,
                            "estimator_noise_sigma": noise,
                            "routing_eligibility": eligibility,
                            "reservation_multiplier": reservation_multiplier,
                            "reservation_mode": config.reservation_mode,
                            "reservation_quantile": config.reservation_quantile,
                            "output_cap": config.output_cap,
                            "model_output_caps": json.dumps(dict(config.model_output_caps), sort_keys=True),
                            "routed_output_length_multiplier": output_multiplier,
                            "hindsight_max_count": benchmark_max.admitted_count,
                            "hindsight_max_min_rate": min(benchmark_min.completion_rates.values(), default=0.0),
                            "runtime_seconds": runtime_seconds,
                        }
                        metrics["gap_to_max_count_hindsight"] = benchmark_max.admitted_count - metrics["completed_total"]
                        metrics["gap_to_max_min_rate_hindsight"] = (
                            run_metadata["hindsight_max_min_rate"] - metrics["min_tenant_completion_rate"]
                        )
                        run_rows.append({**run_metadata, **metrics})
                        for tenant_row in run_tenants:
                            tenant_rows.append({**run_metadata, **tenant_row})
                        trace_policy_selected = config.trace_policies is None or policy_name in config.trace_policies
                        if replicate in config.trace_replicates and trace_policy_selected:
                            for event in events:
                                trace_row = asdict(event)
                                trace_row.update(
                                    {
                                        "run_id": run_id,
                                        "budget_fraction": fraction,
                                        "budget_micro_usd": budget,
                                        "workload_kind": workload_kind,
                                        "replicate": replicate,
                                    }
                                )
                                traces.append(trace_row)
                        stride = config.timeseries_stride
                        for index, event in enumerate(events):
                            if index % stride and index != len(events) - 1:
                                continue
                            timeseries.append(
                                {
                                    **run_metadata,
                                    "timestamp": event.timestamp,
                                    "request_id": event.request_id,
                                    "global_remaining_micro_usd": event.global_remaining,
                                    "cumulative_spend_micro_usd": budget - event.global_remaining,
                                    "reservation_before_micro_usd": event.reservation_before,
                                    "realized_cost_micro_usd": event.realized_cost,
                                    "decision": event.decision,
                                    "outcome": event.outcome,
                                    "cumulative_counts": event.cumulative_counts,
                                }
                            )

        run_df = pd.DataFrame(run_rows)
        comparisons = _paired_comparisons(run_df)
        summary = _summarize(run_df, comparisons)
        regime = _regime_map(comparisons)
        metadata = {
            "data_label": config.data_label,
            "seed": config.seed,
            "catalog_version": self.catalog.version,
            "training_request_count": len(training),
            "evaluation_request_count": len(evaluation),
            "excluded_request_count": excluded,
            "training_window": "chronological leading fraction; used only for the global estimate and threshold tuning",
            "training_quota_weights": training_tenant_weights,
            "evaluation_window": "post-training requests; bootstrap resamples whole UTC calendar days",
            "bootstrap_method": "day-block bootstrap with replacement; tenant mix and intra-day structure preserved within sampled days",
            "bootstrap_sensitivity": {
                "configured_method": config.bootstrap_method,
                "local_block_hours": config.bootstrap_block_hours,
                "local_window_days": config.bootstrap_window_days,
            },
            "paired_design": "same sampled workload, cost multiplier vector, scenario seed, and per-index routing draws for every policy in each scenario",
            "random_streams": {
                "workload": "SeedSequence spawn key 0",
                "cost": "SeedSequence spawn key 1",
                "routing": "SeedSequence spawn key 2",
                "tenant_volume_reweighting": "SeedSequence spawn key 3",
                "scenario_seed_derivation": "SeedSequence spawn key 4",
            },
            "assumptions": [
                "All budgets and eligibility probabilities are modeled scenario assumptions.",
                "Routed outcomes and routed output lengths are counterfactual; no quality equivalence is assumed.",
                "Routed input token counts are held unchanged as an explicit scenario assumption.",
                "Reservation multipliers scale training-window estimated costs; they are sensitivity factors, not empirical estimator modes.",
                "Confidence intervals summarize workload resampling and modeled assumptions, not real-world cost uncertainty.",
                "The fixture label SYNTHETIC TEST DATA does not describe CMU observations or real prices.",
            ],
            "config": asdict(config),
            "experiment_runtime_seconds": time.perf_counter() - experiment_started,
            "scenarios": scenario_metadata,
        }
        return ExperimentResults(
            run_metrics=run_df,
            tenant_metrics=pd.DataFrame(tenant_rows),
            experiment_summary=summary,
            policy_comparisons=comparisons,
            regime_map=regime,
            budget_timeseries=pd.DataFrame(timeseries),
            event_traces=pd.DataFrame(traces),
            scenario_metadata=metadata,
        )


def _paired_comparisons(run_df: pd.DataFrame) -> pd.DataFrame:
    if run_df.empty:
        return pd.DataFrame()
    key_columns = [
        "scenario_id", "budget_fraction", "budget_micro_usd", "replicate", "demand_imbalance",
        "estimator_noise_sigma", "routing_eligibility", "reservation_multiplier", "reservation_mode",
        "reservation_quantile", "output_cap", "model_output_caps", "routed_output_length_multiplier",
    ]
    metric_columns = [
        "completed_total", "completed_original", "completed_routed", "realized_cost_micro_usd",
        "cost_per_completed_request_micro_usd", "min_tenant_completion_rate", "budget_utilization",
    ]
    baseline = run_df[run_df["policy"] == "FCFS"][key_columns + metric_columns].rename(
        columns={column: f"fcfs_{column}" for column in metric_columns}
    )
    policies = run_df[run_df["policy"] != "FCFS"]
    paired = policies.merge(baseline, on=key_columns, how="left", validate="many_to_one")
    for column in metric_columns:
        paired[f"paired_{column}_difference"] = paired[column] - paired[f"fcfs_{column}"]
    return paired


def _summarize(run_df: pd.DataFrame, comparisons: pd.DataFrame) -> pd.DataFrame:
    if run_df.empty:
        return pd.DataFrame()
    group_columns = [
        "policy", "budget_fraction", "demand_imbalance", "estimator_noise_sigma", "routing_eligibility",
        "reservation_multiplier", "reservation_mode", "reservation_quantile", "output_cap", "model_output_caps",
        "routed_output_length_multiplier",
    ]
    metrics = [
        "admitted", "completed_original", "completed_routed", "completed_total", "rejected", "truncated",
        "admission_rate", "completion_rate_original", "completion_rate_routed", "completion_rate_total",
        "realized_cost_micro_usd", "reserved_micro_usd", "unused_reservation_micro_usd", "overrun_micro_usd",
        "cost_per_completed_request_micro_usd", "cost_per_original_completion_micro_usd",
        "cost_per_routed_completion_micro_usd", "budget_utilization", "budget_remaining_micro_usd",
        "budget_remaining_fraction", "runtime_seconds", "min_tenant_completion_rate", "max_min_completion_gap",
        "jain_completion_rate", "gini_completion_rate", "token_weighted_served_share", "cost_weighted_served_share",
        "completion_size_q1", "completion_size_q2", "completion_size_q3", "completion_size_q4",
        "gap_to_max_count_hindsight", "gap_to_max_min_rate_hindsight",
    ]
    rows: list[dict[str, Any]] = []
    comparison_metrics = [
        "paired_completed_total_difference", "paired_realized_cost_micro_usd_difference",
        "paired_min_tenant_completion_rate_difference", "paired_budget_utilization_difference",
    ]
    grouped = run_df.groupby(group_columns, dropna=False, sort=True)
    for keys, group in grouped:
        record = dict(zip(group_columns, keys))
        record["replicates"] = len(group)
        for metric in metrics:
            values = pd.to_numeric(group[metric], errors="coerce").dropna().to_numpy(dtype=float)
            record[f"mean_{metric}"] = float(np.mean(values)) if len(values) else None
            record[f"ci95_low_{metric}"] = float(np.percentile(values, 2.5)) if len(values) else None
            record[f"ci95_high_{metric}"] = float(np.percentile(values, 97.5)) if len(values) else None
        policy_comparisons = comparisons[
            (comparisons["policy"] == record["policy"])
            & (comparisons["budget_fraction"] == record["budget_fraction"])
            & (comparisons["demand_imbalance"] == record["demand_imbalance"])
            & (comparisons["estimator_noise_sigma"] == record["estimator_noise_sigma"])
            & (comparisons["routing_eligibility"] == record["routing_eligibility"])
            & (comparisons["reservation_multiplier"] == record["reservation_multiplier"])
            & (comparisons["routed_output_length_multiplier"] == record["routed_output_length_multiplier"])
        ] if not comparisons.empty else pd.DataFrame()
        for metric in comparison_metrics:
            values = (
                pd.to_numeric(policy_comparisons[metric], errors="coerce").dropna().to_numpy(dtype=float)
                if metric in policy_comparisons
                else np.asarray([], dtype=float)
            )
            record[f"mean_{metric}"] = float(np.mean(values)) if len(values) else (0.0 if record["policy"] == "FCFS" else None)
            record[f"ci95_low_{metric}"] = float(np.percentile(values, 2.5)) if len(values) else (0.0 if record["policy"] == "FCFS" else None)
            record[f"ci95_high_{metric}"] = float(np.percentile(values, 97.5)) if len(values) else (0.0 if record["policy"] == "FCFS" else None)
            record[f"win_rate_{metric}"] = float(np.mean(values > 0)) if len(values) else (0.0 if record["policy"] == "FCFS" else None)
            standard_deviation = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
            record[f"effect_size_{metric}"] = float(np.mean(values) / standard_deviation) if standard_deviation else None
        rows.append(record)
    return pd.DataFrame(rows)


def _regime_map(comparisons: pd.DataFrame) -> pd.DataFrame:
    if comparisons.empty:
        return pd.DataFrame()
    group_columns = ["policy", "budget_fraction", "demand_imbalance", "estimator_noise_sigma"]
    result = (
        comparisons.groupby(group_columns, dropna=False, sort=True)[
            ["paired_completed_total_difference", "paired_min_tenant_completion_rate_difference", "paired_budget_utilization_difference"]
        ]
        .mean()
        .reset_index()
    )
    result = result.rename(
        columns={
            "demand_imbalance": "imbalance_regime",
            "estimator_noise_sigma": "uncertainty_regime",
            "paired_completed_total_difference": "completion_advantage_over_fcfs",
            "paired_min_tenant_completion_rate_difference": "min_tenant_rate_advantage_over_fcfs",
            "paired_budget_utilization_difference": "budget_utilization_advantage_over_fcfs",
        }
    )
    return result
