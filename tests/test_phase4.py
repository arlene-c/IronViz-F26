from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ironviz_f26.experiments import (
    DEFAULT_POLICIES,
    ExperimentConfig,
    ExperimentRunner,
    day_block_bootstrap,
    local_block_bootstrap,
)
from ironviz_f26.fixture import generate_fixture
from ironviz_f26.outputs import write_outputs
from ironviz_f26.pricing import PriceCatalog, PriceRecord


CATALOG = PriceCatalog(
    version="phase4-synthetic-test",
    rows={
        ("openai", "gpt-4o"): PriceRecord("openai", "gpt-4o", 150, 40, 250),
        ("openai", "gpt-4o-mini"): PriceRecord("openai", "gpt-4o-mini", 80, 20, 120),
        ("anthropic", "claude-3.5-sonnet"): PriceRecord("anthropic", "claude-3.5-sonnet", 140, 35, 230),
    },
)


def test_day_block_bootstrap_is_reproducible_and_multiday() -> None:
    rows = generate_fixture(seed=55, n_requests=48)
    first = day_block_bootstrap(rows, seed=101, replicate=2)
    second = day_block_bootstrap(rows, seed=101, replicate=2)

    assert len({row["timestamp"][:10] for row in rows}) == 2
    assert first == second
    assert len(first) == len(rows)
    assert len({row["request_id"] for row in first}) == len(first)
    assert len({row["timestamp"][:10] for row in first}) == 2
    assert all("source_request_id" in row for row in first)


def test_local_12_hour_bootstrap_is_reproducible_and_preserves_source_rows() -> None:
    rows = generate_fixture(seed=91, n_requests=96, requests_per_day=24)
    first = local_block_bootstrap(rows, seed=1337, replicate=4, block_hours=12, window_days=3)
    second = local_block_bootstrap(rows, seed=1337, replicate=4, block_hours=12, window_days=3)
    source_by_id = {row["request_id"]: row for row in rows}

    assert first == second
    assert first == sorted(first, key=lambda row: (row["timestamp"], row["request_id"]))
    assert len({row["request_id"] for row in first}) == len(first)
    for row in first:
        source = source_by_id[row["source_request_id"]]
        for field in ("tenant", "provider", "model", "input_tokens", "output_tokens", "cached_input_tokens"):
            assert row[field] == source[field]


def test_training_reservation_modes_use_training_only_outputs() -> None:
    reservation_catalog = PriceCatalog(
        version="synthetic-reservation-test",
        rows={("test", "high"): PriceRecord("test", "high", 0, 0, 1_000_000)},
    )
    rows = [
        {
            "request_id": f"r{index}",
            "timestamp": f"2026-01-01T00:00:0{index}Z",
            "provider": "test",
            "model": "high",
            "tenant": "tenant-a",
            "input_tokens": 0,
            "output_tokens": output_tokens,
            "cached_input_tokens": 0,
            "original_status": "success",
        }
        for index, output_tokens in enumerate((10, 30, 80, 100))
    ]
    observed_estimates = {}
    for mode in ("mean", "quantile", "cap"):
        config = ExperimentConfig(
            budget_fractions=(1.0,),
            replicates=1,
            training_fraction=0.5,
            bootstrap=False,
            demand_imbalance=(1.0,),
            estimator_noise=(0.0,),
            routing_eligibility=(0.0,),
            reservation_multipliers=(1.0,),
            routed_output_multipliers=(0.7,),
            policies=("FCFS",),
            reservation_mode=mode,
            reservation_quantile=0.75,
            output_cap=100,
            model_output_caps={"high": 40},
            trace_replicates=(0,),
        )
        results = ExperimentRunner(reservation_catalog, config).run(rows)
        evaluation_estimates = results.event_traces.sort_values("timestamp")["estimated_cost"].tolist()
        observed_estimates[mode] = evaluation_estimates

    assert observed_estimates == {"mean": [20, 20], "quantile": [25, 25], "cap": [40, 40]}

    changed_future = [dict(row) for row in rows]
    changed_future[2]["output_tokens"] = 800
    changed_future[3]["output_tokens"] = 1000
    mean_config = ExperimentConfig(
        budget_fractions=(1.0,),
        replicates=1,
        training_fraction=0.5,
        bootstrap=False,
        demand_imbalance=(1.0,),
        estimator_noise=(0.0,),
        routing_eligibility=(0.0,),
        reservation_multipliers=(1.0,),
        routed_output_multipliers=(0.7,),
        policies=("FCFS",),
        reservation_mode="mean",
        output_cap=100,
        trace_replicates=(0,),
    )
    perturbed = ExperimentRunner(reservation_catalog, mean_config).run(changed_future)
    assert perturbed.event_traces.sort_values("timestamp")["estimated_cost"].tolist() == [20, 20]


def test_strict_output_cap_truncates_and_settles_without_overspend() -> None:
    from ironviz_f26.engine import SimulationEngine
    from ironviz_f26.estimators import GlobalEstimator
    from ironviz_f26.policies import FCFS

    catalog = PriceCatalog(
        version="strict-cap-test",
        rows={("test", "high"): PriceRecord("test", "high", 0, 0, 1_000_000)},
    )
    row = {
        "request_id": "cap-r1",
        "timestamp": "2026-01-01T00:00:00Z",
        "provider": "test",
        "model": "high",
        "tenant": "tenant-a",
        "input_tokens": 0,
        "output_tokens": 10,
        "cached_input_tokens": 0,
        "original_status": "success",
    }
    engine = SimulationEngine(
        catalog=catalog,
        policy=FCFS(),
        budget=100,
        estimator=GlobalEstimator([20]),
        strict_mode=True,
        output_caps={"high": 5},
    )

    event = engine.run([row])[0]

    assert event.outcome == "TRUNCATED_ORIGINAL"
    assert event.allowed_output_tokens == 5
    assert event.realized_cost == 5
    assert event.overrun == 0
    assert engine.ledger.global_spent == 5
    assert engine.ledger.global_remaining == 95


def test_runner_pairs_workload_cost_and_routing_draws(tmp_path: Path) -> None:
    rows = generate_fixture(seed=77, n_requests=48)
    config = ExperimentConfig(
        budget_fractions=(0.7,),
        replicates=2,
        seed=303,
        training_fraction=0.25,
        demand_imbalance=(1.0,),
        estimator_noise=(0.0, 0.2),
        routing_eligibility=(0.0, 0.5, 1.0),
        reservation_multipliers=(1.0,),
        routed_output_multipliers=(0.7, 1.0),
        policies=DEFAULT_POLICIES,
        trace_replicates=(0, 1),
        data_label="SYNTHETIC TEST DATA",
    )
    results = ExperimentRunner(CATALOG, config).run(rows)

    assert len(results.run_metrics) == 2 * 2 * 3 * 2 * len(DEFAULT_POLICIES)
    assert results.run_metrics["runtime_seconds"].ge(0).all()
    traced = results.event_traces
    for _, scenario_rows in traced.groupby("scenario_id"):
        assert scenario_rows.groupby("policy")["request_id"].apply(tuple).nunique() == 1
        assert scenario_rows.groupby("request_id")["cost_uncertainty_multiplier"].nunique().max() == 1
    routed = traced[traced["policy"].str.contains("Routing", na=False)]
    assert routed.groupby(["scenario_id", "request_id"])["modeled_routed_output_tokens"].nunique().max() == 1
    assert set(results.policy_comparisons["policy"]) == set(DEFAULT_POLICIES) - {"FCFS"}
    assert {"paired_completed_total_difference", "paired_min_tenant_completion_rate_difference"}.issubset(
        results.policy_comparisons.columns
    )


def test_output_writer_creates_contract_tables_and_charts(tmp_path: Path) -> None:
    rows = generate_fixture(seed=19, n_requests=24)
    config = ExperimentConfig(
        budget_fractions=(0.5, 0.7, 0.85, 1.0),
        replicates=1,
        training_fraction=0.25,
        bootstrap=False,
        demand_imbalance=(1.0,),
        estimator_noise=(0.0,),
        routing_eligibility=(0.5,),
        reservation_multipliers=(1.0,),
        routed_output_multipliers=(0.7,),
        policies=DEFAULT_POLICIES,
        trace_replicates=(0,),
        data_label="SYNTHETIC TEST DATA",
    )
    results = ExperimentRunner(CATALOG, config).run(rows)
    paths = write_outputs(results, tmp_path)

    expected = {
        "event_traces.parquet",
        "budget_timeseries.parquet",
        "run_metrics.csv",
        "tenant_metrics.csv",
        "experiment_summary.csv",
        "policy_comparisons.csv",
        "regime_map.csv",
        "scenario_metadata.json",
        "findings.md",
        "completion_vs_budget_fraction.png",
        "per_tenant_completion.png",
        "budget_remaining_over_time.png",
        "paired_differences_ci.png",
        "routing_sensitivity.png",
    }
    assert expected.issubset({path.name for path in paths})
    assert pd.read_parquet(tmp_path / "event_traces.parquet").columns.tolist()[0:6] == [
        "run_id", "scenario_id", "seed", "timestamp", "request_id", "source_request_id"
    ]
    assert pq.read_schema(tmp_path / "event_traces.parquet").field("modeled_routed_output_tokens").type == pa.int64()
    assert "completed_routed" in pd.read_csv(tmp_path / "run_metrics.csv").columns
    assert (tmp_path / "findings.md").read_text(encoding="utf-8").startswith("# Simulation Findings")
    assert all((tmp_path / filename).stat().st_size > 1000 for filename in expected if filename.endswith(".png"))
