from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
import math
from pathlib import Path
import time

import pandas as pd

from ironviz_f26.engine import SimulationEngine
from ironviz_f26.estimators import GlobalEstimator
from ironviz_f26.experiments import modeled_request_cost
from ironviz_f26.money import Money
from ironviz_f26.policies import FCFS
from ironviz_f26.reference_adapter import load_reference_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Full-row FCFS replay with an expanding historical model-output estimator.")
    parser.add_argument("--clean", default="results/clean_requests.csv")
    parser.add_argument("--simulation", default="results/requests_sim.csv")
    parser.add_argument("--prices", default="config/prices.csv")
    parser.add_argument("--output-dir", default="outputs/authoritative_full_fcfs")
    parser.add_argument("--budget-fractions", default="0.5,0.7,0.85,1.0")
    parser.add_argument("--output-cap", type=int, default=1024)
    args = parser.parse_args()

    fractions = tuple(float(value.strip()) for value in args.budget_fractions.split(",") if value.strip())
    if any(not 0 <= fraction <= 1 for fraction in fractions):
        parser.error("budget fractions must lie between 0 and 1")
    adapted = load_reference_outputs(args.clean, args.simulation, args.prices)
    requests = sorted(adapted.requests, key=lambda row: (row.timestamp, row.request_id))
    catalog = adapted.prices
    reference_cost = sum(modeled_request_cost(asdict(request), catalog) for request in requests)
    history: dict[tuple[str, str], tuple[int, int]] = {}
    estimates: dict[tuple[str, str], int] = {}

    for request in requests:
        key = (request.provider, request.model)
        previous_sum, previous_count = history.get(key, (0, 0))
        predicted_output = previous_sum / previous_count if previous_count else 0.0
        cap = args.output_cap
        price = catalog.lookup(request.provider, request.model)
        input_cost = Money.cost_for_tokens(
            request.input_tokens - request.cached_input_tokens,
            price.input_price,
        ) + Money.cost_for_tokens(request.cached_input_tokens, price.cached_input_price)
        estimated_output = min(cap, math.ceil(predicted_output))
        estimates[(request.request_id, request.model)] = input_cost + Money.cost_for_tokens(
            estimated_output,
            price.output_price,
        )
        history[key] = (previous_sum + request.output_tokens, previous_count + 1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_metrics: list[dict[str, object]] = []
    tenant_metrics: list[dict[str, object]] = []
    traces: list[dict[str, object]] = []
    for fraction in fractions:
        budget = int(reference_cost * fraction)
        engine = SimulationEngine(
            catalog=catalog,
            policy=FCFS(),
            budget=budget,
            estimator=GlobalEstimator([0]),
            strict_mode=True,
            output_cap=args.output_cap,
            seed=0,
            scenario_id=f"full-online-fcfs-{fraction:.2f}",
        )
        started = time.perf_counter()
        events = engine.run(requests, estimated_costs=estimates)
        runtime = time.perf_counter() - started
        spend = engine.ledger.global_spent
        assert len(events) == len(requests)
        assert spend == sum(event.realized_cost for event in events)
        assert spend + engine.ledger.global_remaining == budget
        assert engine.ledger.total_reserved() == 0
        assert engine.ledger.global_remaining >= 0
        completed = sum(event.outcome == "COMPLETED_ORIGINAL" for event in events)
        routed_completed = sum(event.outcome == "COMPLETED_ROUTED_CF" for event in events)
        admitted = sum(event.decision == "ADMITTED" for event in events)
        rejected = sum(event.outcome == "REJECTED" for event in events)
        truncated = sum(event.outcome.startswith("TRUNCATED") for event in events)
        first_refusal = next(
            (
                event for event in events
                if event.outcome == "REJECTED" and event.estimated_cost > event.global_remaining
            ),
            None,
        )
        time_to_exhaustion = (
            (
                datetime.fromisoformat(first_refusal.timestamp.replace("Z", "+00:00"))
                - datetime.fromisoformat(requests[0].timestamp.replace("Z", "+00:00"))
            ).total_seconds()
            if first_refusal
            else None
        )
        run_id = f"online-fcfs-{fraction:.2f}"
        run_metrics.append(
            {
                "run_id": run_id,
                "policy": "FCFS",
                "budget_fraction": fraction,
                "budget_micro_usd": budget,
                "reference_cost_micro_usd": reference_cost,
                "request_count": len(requests),
                "admitted": admitted,
                "completed_original": completed,
                "completed_routed": routed_completed,
                "rejected": rejected,
                "truncated": truncated,
                "realized_cost_micro_usd": spend,
                "budget_remaining_micro_usd": engine.ledger.global_remaining,
                "unused_budget_micro_usd": engine.ledger.global_remaining,
                "overrun_micro_usd": sum(event.overrun for event in events),
                "cost_per_original_completion_micro_usd": spend / completed if completed else None,
                "time_to_budget_exhaustion_seconds": time_to_exhaustion,
                "runtime_seconds": runtime,
                "estimator": "expanding per-provider/model mean of prior observed outputs; first-request prior=0",
                "output_cap": args.output_cap,
            }
        )
        for event in events:
            traces.append(asdict(event))
        for tenant in sorted({request.tenant for request in requests}):
            tenant_events = [event for event in events if event.tenant == tenant]
            demand = sum(request.tenant == tenant for request in requests)
            tenant_metrics.append(
                {
                    "run_id": run_id,
                    "tenant": tenant,
                    "demand_requests": demand,
                    "admitted": sum(event.decision == "ADMITTED" for event in tenant_events),
                    "completed_original": sum(event.outcome == "COMPLETED_ORIGINAL" for event in tenant_events),
                    "completed_routed": 0,
                    "rejected": sum(event.outcome == "REJECTED" for event in tenant_events),
                    "truncated": sum(event.outcome.startswith("TRUNCATED") for event in tenant_events),
                    "realized_cost_micro_usd": sum(event.realized_cost for event in tenant_events),
                }
            )

    pd.DataFrame(run_metrics).to_csv(output_dir / "run_metrics.csv", index=False)
    pd.DataFrame(tenant_metrics).to_csv(output_dir / "tenant_metrics.csv", index=False)
    pd.DataFrame(traces).to_parquet(output_dir / "event_traces.parquet", index=False)
    report = {
        "data_label": "CLEANED REFERENCE INPUT; modeled strict-budget simulation",
        "request_count": len(requests),
        "reference_cost_micro_usd": reference_cost,
        "eligible_row_coverage_exact": True,
        "training_evaluation_mode": "online expanding history across all chronological requests",
        "first_request_prior": "zero predicted output tokens for provider/model pairs with no prior observations",
        "future_information": "each request estimate uses only earlier observed output tokens for that provider/model",
        "budget_fractions": fractions,
        "estimator_output_caps": {"default": args.output_cap},
        "randomness": "deterministic, no random estimator or routing draws",
        "runtime_seconds_total": sum(float(row["runtime_seconds"]) for row in run_metrics),
    }
    (output_dir / "run_metadata.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"metadata": report, "runs": run_metrics}, indent=2))


if __name__ == "__main__":
    main()
