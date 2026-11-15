from __future__ import annotations

import math
import pytest

from ironviz_f26.benchmarks import max_count_hindsight, max_min_tenant_hindsight
from ironviz_f26.engine import SimulationEngine
from ironviz_f26.estimators import GlobalEstimator, ModelConditionalEstimator
from ironviz_f26.fixture import generate_fixture
from ironviz_f26.money import Money
from ironviz_f26.policies import AdaptiveSharing, CostThreshold, FCFS, Pacing, Quotas
from ironviz_f26.pricing import PriceCatalog, PriceRecord
from ironviz_f26.routing import RoutingWrapper
from ironviz_f26.state import ObservableState, PreAdmissionView


CATALOG = PriceCatalog(
    version="phase3-synthetic-test",
    rows={
        ("test", "high"): PriceRecord("test", "high", 0, 0, 1_000_000),
        ("test", "low"): PriceRecord("test", "low", 0, 0, 500_000),
        ("openai", "gpt-4o"): PriceRecord("openai", "gpt-4o", 150, 40, 250),
        ("openai", "gpt-4o-mini"): PriceRecord("openai", "gpt-4o-mini", 80, 20, 120),
        ("anthropic", "claude-3.5-sonnet"): PriceRecord("anthropic", "claude-3.5-sonnet", 140, 35, 230),
    },
)


def _request(request_id: str, tenant: str, model: str, output_tokens: int, second: int) -> dict[str, object]:
    return {
        "request_id": request_id,
        "timestamp": f"2026-01-01T00:00:{second:02d}Z",
        "provider": "test",
        "model": model,
        "tenant": tenant,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": output_tokens,
        "original_status": "success",
    }


def _state(remaining: int, spent: dict[str, int] | None = None) -> ObservableState:
    spent = spent or {}
    return ObservableState(
        global_remaining=remaining,
        tenant_remaining={},
        tenant_spent=spent,
        historical_spend=spent,
        counts={},
    )


def _view(tenant: str, cost: int, timestamp: str = "2026-01-01T00:00:00Z", request_id: str = "r") -> PreAdmissionView:
    return PreAdmissionView(
        request_id=request_id,
        timestamp=timestamp,
        tenant=tenant,
        provider="test",
        model="high",
        input_tokens=0,
        cached_input_tokens=0,
        input_cost=0,
        output_price=1_000_000,
        estimated_cost=cost,
    )


def test_adaptive_sharing_borrows_unused_quota_and_improves_utilization() -> None:
    requests = [
        _request("a1", "tenant-a", "high", 60, 0),
        _request("a2", "tenant-a", "high", 60, 1),
        _request("a3", "tenant-a", "high", 60, 2),
        _request("b1", "tenant-b", "low", 10, 3),
    ]
    estimator = ModelConditionalEstimator({"high": [60], "low": [10]})
    quotas_engine = SimulationEngine(
        catalog=CATALOG,
        policy=Quotas(tenant_weights={"tenant-a": 0.5, "tenant-b": 0.5}),
        budget=200,
        estimator=estimator,
    )
    adaptive_policy = AdaptiveSharing(
        tenant_weights={"tenant-a": 0.5, "tenant-b": 0.5},
        rho=0,
        window=10,
        max_borrow_fraction=1,
    )
    adaptive_engine = SimulationEngine(catalog=CATALOG, policy=adaptive_policy, budget=200, estimator=estimator, horizon_start="2026-01-01T00:00:00Z", horizon_end="2026-01-01T00:00:03Z")

    quota_events = quotas_engine.run(requests)
    adaptive_events = adaptive_engine.run(requests)

    quota_spend = quotas_engine.ledger.global_spent
    adaptive_spend = adaptive_engine.ledger.global_spent
    assert sum(event.outcome != "REJECTED" for event in adaptive_events) > sum(
        event.outcome != "REJECTED" for event in quota_events
    )
    assert adaptive_spend > quota_spend
    assert adaptive_policy.lender_debits["tenant-b"] == 80
    assert adaptive_engine.ledger.global_remaining + adaptive_spend == 200
    assert sum(event.realized_cost for event in adaptive_events) == adaptive_spend


def test_adaptive_sharing_never_double_promises_lender_balance() -> None:
    policy = AdaptiveSharing(
        tenant_weights={"tenant-a": 0.5, "tenant-b": 0.5},
        rho=0,
        max_borrow_fraction=1,
    )
    policy.reset(
        {
            "budget": 100,
            "tenants": ["tenant-a", "tenant-b"],
            "start_timestamp": "2026-01-01T00:00:00Z",
            "end_timestamp": "2026-01-01T00:00:10Z",
        }
    )

    assert policy.decide(_view("tenant-a", 90, request_id="first"), _state(100))
    assert policy.lender_debits["tenant-b"] == 40
    assert not policy.decide(_view("tenant-a", 90, request_id="second"), _state(100))
    assert policy.lender_debits["tenant-b"] == 40

    capped_policy = AdaptiveSharing(
        tenant_weights={"tenant-a": 0.5, "tenant-b": 0.5},
        rho=0,
        max_borrow_fraction=0.5,
    )
    capped_policy.reset({"budget": 1000, "tenants": ["tenant-a", "tenant-b"], "start_timestamp": "2026-01-01T00:00:00Z", "end_timestamp": "2026-01-01T00:00:10Z"})
    assert capped_policy.decide(_view("tenant-a", 700, request_id="cap-first"), _state(1000))
    assert capped_policy.borrowed_reserved["tenant-a"] == 200
    assert not capped_policy.decide(_view("tenant-a", 700, request_id="cap-second"), _state(1000))


def test_pacing_obeys_configured_cumulative_target() -> None:
    policy = Pacing(slack=0, target_curve=((0.0, 0.0), (0.5, 0.2), (1.0, 1.0)))
    policy.reset(
        {
            "budget": 100,
            "start_timestamp": "2026-01-01T00:00:00Z",
            "end_timestamp": "2026-01-01T00:00:10Z",
        }
    )

    assert not policy.decide(_view("tenant-a", 10), _state(100))
    halfway = "2026-01-01T00:00:05Z"
    assert policy.decide(_view("tenant-a", 20, halfway), _state(100))
    assert not policy.decide(_view("tenant-a", 21, halfway), _state(80))


def test_cost_threshold_tunes_only_from_training_reservations() -> None:
    policy = CostThreshold().fit([100, 200, 300], budget=300)
    fitted_tau = policy.tau
    assert fitted_tau == 200
    assert not policy.decide(_view("tenant-a", 250, request_id="evaluation-only"), _state(1000))
    assert policy.tau == fitted_tau


def test_soft_mode_charges_realized_cost_and_records_overrun() -> None:
    engine = SimulationEngine(
        catalog=CATALOG,
        policy=FCFS(),
        budget=100,
        estimator=GlobalEstimator([2]),
        strict_mode=False,
        output_cap=5,
    )
    event = engine.run([_request("soft", "tenant-a", "high", 50, 0)])[0]

    assert event.realized_cost == 5
    assert event.reservation_before == 2
    assert event.allowed_output_tokens == 5
    assert event.outcome == "TRUNCATED_ORIGINAL"
    assert event.overrun == 3
    assert engine.ledger.global_spent == 5
    assert engine.ledger.global_remaining == 95
    assert engine.ledger.global_remaining + engine.ledger.global_spent == 100


def test_routing_is_counterfactual_cheaper_and_does_not_add_rejections() -> None:
    requests = [_request(f"r{i}", "tenant-a", "high", 100, i) for i in range(3)]
    estimator = GlobalEstimator([100])
    original_engine = SimulationEngine(catalog=CATALOG, policy=FCFS(), budget=500, estimator=estimator, seed=31)
    routed_policy = RoutingWrapper(
        FCFS(),
        compatibility_map={("test", "high"): ("test", "low")},
        eligibility_probability=1,
        mu_pair=math.log(0.5),
        sigma_pair=0,
    )
    routed_engine = SimulationEngine(catalog=CATALOG, policy=routed_policy, budget=500, estimator=estimator, seed=31)

    original_events = original_engine.run(requests)
    routed_events = routed_engine.run(requests)

    assert sum(event.outcome == "REJECTED" for event in routed_events) <= sum(
        event.outcome == "REJECTED" for event in original_events
    )
    assert routed_engine.ledger.global_spent < original_engine.ledger.global_spent
    assert all(event.outcome == "COMPLETED_ROUTED_CF" for event in routed_events)
    assert all(event.is_counterfactual for event in routed_events)
    assert all(event.observed_original_output_tokens == 100 for event in routed_events)
    assert all(event.modeled_routed_output_tokens == 50 for event in routed_events)
    assert all(event.selected_model == "low" and event.original_model == "high" for event in routed_events)
    assert sum(event.realized_cost for event in routed_events) == routed_engine.ledger.global_spent


def test_routing_respects_explicit_eligibility_and_compatible_pairs() -> None:
    wrapper = RoutingWrapper(
        FCFS(),
        compatibility_map={("test", "high"): ("test", "low")},
        eligible_request_ids=["r1"],
        mu_pair=math.log(0.5),
        sigma_pair=0,
    )
    wrapper.reset({"budget": 100})
    wrapper.prepare_run(2, 5)

    assert wrapper.route_for(0, _view("tenant-a", 10, request_id="r0"), _state(100), CATALOG) is None
    assert wrapper.route_for(1, _view("tenant-a", 10, request_id="r1"), _state(100), CATALOG) == (
        "test",
        "low",
        0.5,
    )


def test_hindsight_benchmarks_match_handcrafted_optima() -> None:
    max_count = max_count_hindsight([8, 3, 5], budget=8)
    assert max_count.admitted_count == 2
    assert max_count.realized_cost == 8
    assert max_count.selected_indices == (1, 2)
    assert max_count.label == "hindsight"

    max_min = max_min_tenant_hindsight(
        ["tenant-a", "tenant-a", "tenant-b", "tenant-b"],
        [1, 100, 1, 100],
        budget=2,
    )
    assert max_min.admitted_count == 2
    assert max_min.realized_cost == 2
    assert max_min.completion_rates == {"tenant-a": 0.5, "tenant-b": 0.5}


def _modeled_cost(request: dict[str, object]) -> int:
    price = CATALOG.lookup(str(request["provider"]), str(request["model"]))
    input_tokens = int(request["input_tokens"])
    cached_tokens = int(request["cached_input_tokens"])
    return (
        Money.cost_for_tokens(input_tokens - cached_tokens, price.input_price)
        + Money.cost_for_tokens(cached_tokens, price.cached_input_price)
        + Money.cost_for_tokens(int(request["output_tokens"]), price.output_price)
    )


@pytest.mark.scenario_sweep
def test_small_scarcity_experiment_fixture_at_50_and_70_percent() -> None:
    fixture = generate_fixture(seed=2026, n_requests=48)
    split = 14
    training, evaluation = fixture[:split], fixture[split:]
    training_costs = [_modeled_cost(row) for row in training]
    evaluation_reference_cost = sum(_modeled_cost(row) for row in evaluation)
    training_reference_cost = sum(training_costs)
    estimator = GlobalEstimator(training_costs)
    compatibility = {
        ("openai", "gpt-4o"): ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-3.5-sonnet"): ("openai", "gpt-4o-mini"),
    }
    results: dict[tuple[float, str], tuple[int, int, int, int]] = {}

    for fraction in (0.5, 0.7):
        budget = max(1, int(evaluation_reference_cost * fraction))
        training_budget = max(1, int(training_reference_cost * fraction))
        threshold = CostThreshold().fit(training_costs, training_budget)
        policies = {
            "FCFS": FCFS(),
            "Quotas": Quotas(),
            "Adaptive": AdaptiveSharing(rho=0.1, window=60, max_borrow_fraction=0.5),
            "Pacing": Pacing(slack=0.15),
            "Threshold": threshold,
            "FCFS+Routing": RoutingWrapper(
                FCFS(),
                compatibility_map=compatibility,
                eligibility_probability=0.5,
                mu_pair=math.log(0.7),
                sigma_pair=0,
            ),
            "Adaptive+Routing": RoutingWrapper(
                AdaptiveSharing(rho=0.1, window=60, max_borrow_fraction=0.5),
                compatibility_map=compatibility,
                eligibility_probability=0.5,
                mu_pair=math.log(0.7),
                sigma_pair=0,
            ),
        }
        benchmark = max_count_hindsight([_modeled_cost(row) for row in evaluation], budget)
        max_min = max_min_tenant_hindsight(
            [str(row["tenant"]) for row in evaluation],
            [_modeled_cost(row) for row in evaluation],
            budget,
        )
        for name, policy in policies.items():
            engine = SimulationEngine(
                catalog=CATALOG,
                policy=policy,
                budget=budget,
                estimator=estimator,
                seed=2026,
                scenario_id=f"fixture-{fraction:.1f}-{name}",
                tenant_roster=("tenant-a", "tenant-b", "tenant-c"),
                horizon_start="2026-01-01T00:00:00Z", horizon_end="2026-01-31T23:59:59Z",
            )
            events = engine.run(evaluation)
            completed = sum(event.outcome in {"COMPLETED_ORIGINAL", "COMPLETED_ROUTED_CF"} for event in events)
            routed_completed = sum(event.outcome == "COMPLETED_ROUTED_CF" for event in events)
            rejected = sum(event.outcome == "REJECTED" for event in events)
            realized_cost = engine.ledger.global_spent
            demand_by_tenant = {
                str(row["tenant"]): sum(other["tenant"] == row["tenant"] for other in evaluation)
                for row in evaluation
            }
            completed_by_tenant = {
                tenant: sum(
                    event.tenant == tenant
                    and event.outcome in {"COMPLETED_ORIGINAL", "COMPLETED_ROUTED_CF"}
                    for event in events
                )
                for tenant in demand_by_tenant
            }
            policy_min_rate = min(
                completed_by_tenant[tenant] / demand_by_tenant[tenant] for tenant in demand_by_tenant
            )
            max_min_rate = min(max_min.completion_rates.values(), default=0.0)
            assert sum(event.realized_cost for event in events) == realized_cost
            assert engine.ledger.global_remaining + realized_cost == budget
            assert engine.ledger.total_reserved() == 0
            results[(fraction, name)] = (completed, routed_completed, rejected, realized_cost)
            print(
                "FIXTURE",
                f"fraction={fraction:.1f}",
                f"policy={name}",
                f"completed={completed}",
                f"original_completed={completed - routed_completed}",
                f"routed_completed={routed_completed}",
                f"rejected={rejected}",
                f"realized_cost_micro_usd={realized_cost}",
                f"gap_to_max_count={benchmark.admitted_count - completed}",
                f"gap_to_max_min_rate={max_min_rate - policy_min_rate:.3f}",
            )

    assert len(results) == 14
