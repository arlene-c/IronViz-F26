from __future__ import annotations

from dataclasses import replace

import pytest

from ironviz_f26.estimators import GlobalEstimator
from ironviz_f26.fixture import generate_fixture
from ironviz_f26.policies import FCFS, Quotas
from ironviz_f26.pricing import PriceCatalog, PriceRecord
from ironviz_f26.state import ObservableState, PreAdmissionView
from ironviz_f26.engine import SimulationEngine


CATALOG = PriceCatalog(
    version="phase2-fixture",
    rows={
        ("openai", "gpt-4o"): PriceRecord(
            provider="openai",
            model="gpt-4o",
            input_price=150,
            cached_input_price=40,
            output_price=250,
        ),
        ("openai", "gpt-4o-mini"): PriceRecord(
            provider="openai",
            model="gpt-4o-mini",
            input_price=80,
            cached_input_price=20,
            output_price=120,
        ),
        ("anthropic", "claude-3.5-sonnet"): PriceRecord(
            provider="anthropic",
            model="claude-3.5-sonnet",
            input_price=140,
            cached_input_price=35,
            output_price=230,
        ),
    },
)


def test_pre_admission_view_hides_realized_values() -> None:
    view = PreAdmissionView(
        request_id="r1",
        timestamp="2026-01-01T00:00:00Z",
        tenant="tenant-a",
        provider="openai",
        model="gpt-4o",
        input_tokens=1000,
        cached_input_tokens=200,
        input_cost=100,
        output_price=250,
        estimated_cost=300,
    )
    state = ObservableState(
        global_remaining=1000,
        tenant_remaining={"tenant-a": 900},
        tenant_spent={"tenant-a": 100},
        historical_spend={"tenant-a": 100},
        counts={"tenant-a": 1},
    )

    forbidden_fields = {
        "output_tokens",
        "realized_output_tokens",
        "realized_cost",
        "future_requests",
        "request_cost",
    }
    assert forbidden_fields.isdisjoint(view.__slots__)
    assert forbidden_fields.isdisjoint(state.__slots__)
    assert state.global_remaining == 1000
    assert "future_requests" not in state.__slots__
    with pytest.raises(TypeError):
        state.tenant_remaining["tenant-a"] = 0


def test_quotas_enforce_handcrafted_tenant_allocations() -> None:
    policy = Quotas(tenant_weights={"tenant-a": 0.25, "tenant-b": 0.75})
    policy.reset({"budget": 1000})
    state = ObservableState(
        global_remaining=1000,
        tenant_remaining={},
        tenant_spent={},
        historical_spend={},
        counts={},
    )
    view = PreAdmissionView(
        request_id="r1",
        timestamp="2026-01-01T00:00:00Z",
        tenant="tenant-a",
        provider="openai",
        model="gpt-4o",
        input_tokens=100,
        cached_input_tokens=0,
        input_cost=1,
        output_price=250,
        estimated_cost=300,
    )

    assert not policy.decide(view, state)
    assert policy.decide(replace(view, tenant="tenant-b"), state)


def test_fcfs_zero_budget_rejects_all_requests() -> None:
    requests = [
        {
            "request_id": f"r{i}",
            "timestamp": f"2026-01-01T00:00:{i:02d}Z",
            "provider": "openai",
            "model": "gpt-4o",
            "tenant": "tenant-a",
            "input_tokens": 1000,
            "output_tokens": 200,
            "cached_input_tokens": 0,
            "original_status": "success",
        }
        for i in range(3)
    ]
    engine = SimulationEngine(
        catalog=CATALOG,
        policy=FCFS(),
        budget=0,
        estimator=GlobalEstimator([100, 200]),
    )
    events = engine.run(requests)

    assert len(events) == 3
    assert all(event.outcome == "REJECTED" for event in events)
    assert engine.ledger.global_remaining == 0


def test_fcfs_and_quotas_reconcile_accounting() -> None:
    requests = [
        {
            "request_id": "r1",
            "timestamp": "2026-01-01T00:00:00Z",
            "provider": "openai",
            "model": "gpt-4o",
            "tenant": "tenant-a",
            "input_tokens": 1000,
            "output_tokens": 100,
            "cached_input_tokens": 0,
            "original_status": "success",
        },
        {
            "request_id": "r2",
            "timestamp": "2026-01-01T00:00:01Z",
            "provider": "openai",
            "model": "gpt-4o",
            "tenant": "tenant-a",
            "input_tokens": 1000,
            "output_tokens": 100,
            "cached_input_tokens": 0,
            "original_status": "success",
        },
        {
            "request_id": "r3",
            "timestamp": "2026-01-01T00:00:02Z",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "tenant": "tenant-b",
            "input_tokens": 600,
            "output_tokens": 50,
            "cached_input_tokens": 0,
            "original_status": "success",
        },
    ]

    fcfs_engine = SimulationEngine(
        catalog=CATALOG,
        policy=FCFS(),
        budget=5000,
        estimator=GlobalEstimator([150, 120]),
    )
    fcfs_events = fcfs_engine.run(requests)

    quotas_engine = SimulationEngine(
        catalog=CATALOG,
        policy=Quotas(tenant_weights={"tenant-a": 0.75, "tenant-b": 0.25}),
        budget=5000,
        estimator=GlobalEstimator([150, 120]),
    )
    quota_events = quotas_engine.run(requests)

    assert sum(event.realized_cost for event in fcfs_events) == fcfs_engine.ledger.global_spent
    assert sum(event.realized_cost for event in quota_events) == quotas_engine.ledger.global_spent
    assert all(event.outcome in {"REJECTED", "COMPLETED_ORIGINAL", "TRUNCATED_ORIGINAL"} for event in fcfs_events)
    assert all(event.tenant in {"tenant-a", "tenant-b"} for event in quota_events)
    assert fcfs_engine.ledger.global_remaining + fcfs_engine.ledger.global_spent == 5000
    assert quotas_engine.ledger.global_remaining + quotas_engine.ledger.global_spent == 5000
    assert [event.realized_cost for event in fcfs_events if event.outcome != "REJECTED"]
    assert sum(event.realized_cost for event in quota_events) == quotas_engine.ledger.global_spent
    assert [event.outcome for event in quota_events] == ["COMPLETED_ORIGINAL", "COMPLETED_ORIGINAL", "COMPLETED_ORIGINAL"]


def test_metamorphic_and_determinism() -> None:
    fixture = generate_fixture(seed=7, n_requests=12, tenants=["tenant-a", "tenant-b"], providers=["openai", "anthropic"])
    cutoff = len(fixture) // 2
    prefix = fixture[:cutoff]
    modified_suffix = [
        {
            **row,
            "tenant": "tenant-z",
            "request_id": f"mutated-{row['request_id']}",
            "output_tokens": max(1, row["output_tokens"] + 100),
        }
        for row in fixture[cutoff:]
    ]
    mutated = prefix + modified_suffix

    engine_a = SimulationEngine(catalog=CATALOG, policy=FCFS(), budget=20000, estimator=GlobalEstimator([150, 120]))
    engine_b = SimulationEngine(catalog=CATALOG, policy=FCFS(), budget=20000, estimator=GlobalEstimator([150, 120]))
    engine_c = SimulationEngine(catalog=CATALOG, policy=FCFS(), budget=20000, estimator=GlobalEstimator([150, 120]))

    results_a = engine_a.run(fixture)
    results_b = engine_b.run(mutated)
    results_c = engine_c.run(fixture)

    assert [event.decision for event in results_a[:cutoff]] == [event.decision for event in results_b[:cutoff]]
    assert [event.request_id for event in results_a[:cutoff]] == [event.request_id for event in results_b[:cutoff]]
    assert results_a == results_c
    assert len(results_a) == len(fixture)


def test_fixture_generator_produces_valid_rows() -> None:
    rows = generate_fixture(seed=11, n_requests=10, tenants=["tenant-a", "tenant-b"], providers=["openai", "anthropic"])
    repeated_rows = generate_fixture(seed=11, n_requests=10, tenants=["tenant-a", "tenant-b"], providers=["openai", "anthropic"])
    assert len(rows) == 10
    assert rows == repeated_rows
    assert all("request_id" in row for row in rows)
    assert all(row["original_status"] == "success" for row in rows)
    assert all(row["input_tokens"] > 0 for row in rows)
    assert all(row["output_tokens"] >= 1 for row in rows)
    assert len({row["model"] for row in rows}) >= 3
    assert sum(row["tenant"] == "tenant-a" for row in rows) > sum(row["tenant"] == "tenant-b" for row in rows)


def test_fcfs_fixture_end_to_end() -> None:
    rows = generate_fixture(seed=2026, n_requests=120)
    budget = 3000
    engine = SimulationEngine(
        catalog=CATALOG,
        policy=FCFS(),
        budget=budget,
        estimator=GlobalEstimator([150, 120]),
        seed=2026,
        scenario_id="phase2-e2e-fixture",
    )

    events = engine.run(rows)

    assert len(events) == len(rows)
    assert sum(event.realized_cost for event in events) == engine.ledger.global_spent
    assert engine.ledger.global_remaining + engine.ledger.global_spent == budget
    assert engine.ledger.total_reserved() == 0
    assert all(event.global_remaining >= 0 for event in events)
    print(
        "FIXTURE",
        "requests", len(rows),
        "events", len(events),
        "admitted", sum(event.decision == "ADMITTED" for event in events),
        "rejected", sum(event.outcome == "REJECTED" for event in events),
        "completed", sum(event.outcome == "COMPLETED_ORIGINAL" for event in events),
        "truncated", sum(event.outcome == "TRUNCATED_ORIGINAL" for event in events),
        "realized_cost_micro_usd", engine.ledger.global_spent,
        "global_remaining_micro_usd", engine.ledger.global_remaining,
        "outstanding_reserved_micro_usd", engine.ledger.total_reserved(),
    )
