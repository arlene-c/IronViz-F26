from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import ironviz_experiments as legacy
from ironviz_f26.engine import SimulationEngine
from ironviz_f26.estimators import GlobalEstimator
from ironviz_f26.policies import FCFS
from ironviz_f26.reference_adapter import load_reference_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare modular FCFS with the data team's legacy reference algorithm.")
    parser.add_argument("--clean", default="results/clean_requests.csv")
    parser.add_argument("--simulation", default="results/requests_sim.csv")
    parser.add_argument("--prices", default="config/prices.csv")
    parser.add_argument("--reference-results", default="results/results.csv")
    parser.add_argument("--output-dir", default="outputs/reference_reconciliation")
    args = parser.parse_args()

    started = time.perf_counter()
    adapted = load_reference_outputs(args.clean, args.simulation, args.prices)
    simulation = pd.read_csv(args.simulation)
    simulation["timestamp"] = pd.to_datetime(simulation["timestamp"], utc=True)
    prices = legacy.read_prices(args.prices)
    tenants = sorted(simulation.tenant.astype(str).unique())
    arrays = legacy.Arrays(simulation, prices, simulation.expected_output_tokens.to_numpy(), tenants)
    reference_usd = float(arrays.real.sum())
    spend_by_tenant = pd.Series(arrays.real).groupby(arrays.tenant).sum().reindex(range(len(tenants))).values
    quota_shares = spend_by_tenant / reference_usd
    legacy_workload = arrays.take(np.arange(len(simulation)), arrays.tfrac)
    expected_micro = np.rint(arrays.exp * 1_000_000).astype(np.int64)

    modular_ids = [request.request_id for request in adapted.requests]
    legacy_ids = simulation.request_id.astype(str).tolist()
    if modular_ids != legacy_ids:
        raise ValueError("Canonical adapter ordering does not match the legacy simulator ordering")
    expected_costs = {
        (request.request_id, request.model): int(expected_micro[index])
        for index, request in enumerate(adapted.requests)
    }
    compatibility_output_caps = {
        str(model): int(max(1024, values.max()))
        for model, values in simulation.groupby("model")["output_tokens"]
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    comparisons: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    reference_summary = pd.read_csv(args.reference_results)

    for fraction in (1.0, 0.85, 0.7, 0.5):
        legacy_budget_usd = reference_usd * fraction
        modular_budget = int(round(legacy_budget_usd * 1_000_000))
        legacy_admitted, _, legacy_charged, _, legacy_first_refusal = legacy.run(
            "fcfs", legacy_budget_usd, quota_shares, legacy_workload
        )
        engine = SimulationEngine(
            catalog=adapted.prices,
            policy=FCFS(),
            budget=modular_budget,
            estimator=GlobalEstimator([0]),
            strict_mode=False,
            output_cap=max(compatibility_output_caps.values(), default=1024),
            output_caps=compatibility_output_caps,
            seed=7,
            scenario_id=f"legacy-fcfs-compat-{int(fraction * 100)}",
        )
        modular_events = engine.run(adapted.requests, estimated_costs=expected_costs)
        modular_by_id = {event.request_id: event for event in modular_events}
        modular_admitted = np.asarray([modular_by_id[request_id].decision == "ADMITTED" for request_id in legacy_ids])
        if len(legacy_admitted) != len(modular_admitted):
            raise AssertionError("Legacy and modular FCFS outputs have different request counts")

        legacy_first = int(np.flatnonzero(~legacy_admitted)[0]) if (~legacy_admitted).any() else -1
        modular_first = int(np.flatnonzero(~modular_admitted)[0]) if (~modular_admitted).any() else -1
        divergences = np.flatnonzero(legacy_admitted != modular_admitted)
        first_divergence = int(divergences[0]) if len(divergences) else -1
        legacy_cumulative_spend = 0.0
        for index, request_id in enumerate(legacy_ids):
            event = modular_by_id[request_id]
            legacy_cost_usd = float(legacy_charged[index])
            legacy_cumulative_spend += legacy_cost_usd
            legacy_remaining = legacy_budget_usd - legacy_cumulative_spend
            comparisons.append(
                {
                    "budget_fraction": fraction,
                    "request_index": index,
                    "request_id": request_id,
                    "timestamp": str(simulation.timestamp.iloc[index]),
                    "legacy_estimated_cost_usd": float(arrays.exp[index]),
                    "modular_estimated_cost_micro_usd": event.estimated_cost,
                    "legacy_admitted": bool(legacy_admitted[index]),
                    "modular_admitted": bool(modular_admitted[index]),
                    "legacy_realized_cost_usd": legacy_cost_usd,
                    "modular_realized_cost_micro_usd": event.realized_cost,
                    "legacy_remaining_budget_usd": legacy_remaining,
                    "modular_remaining_budget_micro_usd": event.global_remaining,
                    "legacy_completion_status": "COMPLETED" if legacy_admitted[index] else "REJECTED",
                    "modular_outcome": event.outcome,
                }
            )
        divergence_cause = "No admission divergence"
        divergence_request = None
        if first_divergence >= 0:
            index = first_divergence
            divergence_request = legacy_ids[index]
            previous_modular_remaining = modular_budget if index == 0 else modular_events[index - 1].global_remaining
            previous_legacy_remaining = legacy_budget_usd - float(np.sum(legacy_charged[:index]))
            expected_difference_micro = float(expected_micro[index]) - float(arrays.exp[index] * 1_000_000)
            if expected_difference_micro:
                divergence_cause = "Per-request expected-cost USD-to-integer-micro rounding"
            elif abs(previous_legacy_remaining * 1_000_000 - previous_modular_remaining) > 1:
                divergence_cause = "Accumulated realized-cost rounding changed remaining pool before this decision"
            elif abs(legacy_budget_usd * 1_000_000 - modular_budget) > 0.5:
                divergence_cause = "Initial budget conversion to integer micro-USD"
            else:
                divergence_cause = "Unclassified algorithm/ordering difference; inspect request-level comparison"

        ref_rows = reference_summary[
            (reference_summary.policy == "fcfs")
            & (reference_summary.budget_pct == int(fraction * 100))
            & (reference_summary.run_id == 0)
        ]
        summaries.append(
            {
                "budget_fraction": fraction,
                "legacy_reference_cost_usd": reference_usd,
                "legacy_budget_usd": legacy_budget_usd,
                "modular_budget_micro_usd": modular_budget,
                "legacy_admitted": int(legacy_admitted.sum()),
                "modular_admitted": int(modular_admitted.sum()),
                "legacy_first_refusal_day_fraction": legacy_first_refusal,
                "legacy_first_refusal_timestamp": str(simulation.timestamp.iloc[legacy_first]) if legacy_first >= 0 else None,
                "modular_first_refusal_timestamp": str(simulation.timestamp.iloc[modular_first]) if modular_first >= 0 else None,
                "first_divergence_request_id": divergence_request,
                "first_divergence_cause": divergence_cause,
                "admission_divergence_count": int(len(divergences)),
                "legacy_realized_cost_usd": float(legacy_charged.sum()),
                "modular_realized_cost_micro_usd": engine.ledger.global_spent,
                "modular_estimator_overrun_micro_usd": sum(event.overrun for event in modular_events),
                "modular_global_budget_overspend_micro_usd": max(0, engine.ledger.global_spent - modular_budget),
                "reference_results_admitted_pct": float(ref_rows.admitted_pct.iloc[0]) if len(ref_rows) else None,
                "soft_compatibility_mode": True,
            }
        )

    comparison_path = output_dir / "request_comparison.csv"
    summary_path = output_dir / "budget_summary.csv"
    pd.DataFrame(comparisons).to_csv(comparison_path, index=False)
    pd.DataFrame(summaries).to_csv(summary_path, index=False)
    report = {
        "reference_pipeline": "src/ironviz_experiments.py as committed on origin/main",
        "compatibility_estimator": "expected_cost from committed requests_sim.csv, rounded to integer micro-USD per request",
        "routing": "disabled",
        "budget_semantics": "legacy expected-cost admission with realized-cost settlement; modular run uses strict_mode=False for compatibility only",
        "canonical_simulator": "unchanged strict mode; compatibility results are not authoritative policy results",
        "rounding_difference": adapted.rounding_reconciliation,
        "summaries": summaries,
        "runtime_seconds": time.perf_counter() - started,
        "outputs": [str(comparison_path), str(summary_path)],
    }
    (output_dir / "reconciliation_metadata.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
