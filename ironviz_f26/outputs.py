from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .experiments import ExperimentResults

TRACE_COLUMNS = [
    "run_id", "scenario_id", "seed", "timestamp", "request_id", "source_request_id", "tenant",
    "original_model", "selected_model", "policy", "decision", "outcome", "estimated_cost",
    "reservation_before", "reservation_after_settlement", "realized_cost", "global_remaining",
    "tenant_remaining", "cumulative_counts", "is_counterfactual", "observed_original_output_tokens",
    "modeled_routed_output_tokens", "allowed_output_tokens", "overrun", "cost_uncertainty_multiplier",
    "budget_fraction", "budget_micro_usd", "workload_kind", "replicate",
]
TIMESERIES_COLUMNS = [
    "run_id", "scenario_id", "seed", "policy", "budget_fraction", "budget_micro_usd", "replicate",
    "workload_kind", "demand_imbalance", "estimator_noise_sigma", "routing_eligibility",
    "reservation_multiplier", "routed_output_length_multiplier", "timestamp", "request_id",
    "global_remaining_micro_usd", "cumulative_spend_micro_usd", "reservation_before_micro_usd",
    "realized_cost_micro_usd", "decision", "outcome", "cumulative_counts",
]
METRIC_COLUMNS = [
    "request_count", "admitted", "completed_original", "completed_routed", "completed_total", "rejected",
    "truncated", "admission_rate", "completion_rate_original", "completion_rate_routed", "completion_rate_total",
    "realized_cost_micro_usd", "reserved_micro_usd", "unused_reservation_micro_usd", "overrun_micro_usd",
    "cost_per_completed_request_micro_usd", "cost_per_original_completion_micro_usd",
    "cost_per_routed_completion_micro_usd", "budget_utilization", "budget_remaining_micro_usd",
    "budget_remaining_fraction", "time_to_budget_exhaustion_seconds", "min_tenant_completion_rate",
    "max_min_completion_gap", "jain_completion_rate", "gini_completion_rate", "token_weighted_served_share",
    "cost_weighted_served_share", "reference_cost_micro_usd", "completion_size_q1", "completion_size_q2",
    "completion_size_q3", "completion_size_q4", "gap_to_max_count_hindsight", "gap_to_max_min_rate_hindsight",
]
RUN_META_COLUMNS = [
    "run_id", "scenario_id", "seed", "policy", "budget_fraction", "budget_micro_usd", "replicate",
    "workload_kind", "demand_imbalance", "estimator_noise_sigma", "routing_eligibility",
    "reservation_multiplier", "reservation_mode", "reservation_quantile", "output_cap", "model_output_caps",
    "routed_output_length_multiplier", "hindsight_max_count", "hindsight_max_min_rate", "runtime_seconds",
]
TENANT_COLUMNS = [
    "tenant", "demand_requests", "admitted", "completed_original", "completed_routed", "completed_total",
    "rejected", "truncated", "admission_rate", "completion_rate_original", "completion_rate_routed",
    "completion_rate_total", "realized_cost_micro_usd", "reference_cost_micro_usd", "spend_share",
    "demand_share", "token_weighted_served_share", "cost_weighted_served_share",
]
TENANT_META_COLUMNS = RUN_META_COLUMNS + TENANT_COLUMNS
COMPARISON_KEYS = [
    "scenario_id", "budget_fraction", "budget_micro_usd", "replicate", "demand_imbalance",
    "estimator_noise_sigma", "routing_eligibility", "reservation_multiplier", "routed_output_length_multiplier",
]
PAIRED_METRICS = [
    "completed_total", "completed_original", "completed_routed", "realized_cost_micro_usd",
    "cost_per_completed_request_micro_usd", "min_tenant_completion_rate", "budget_utilization",
]
COMPARISON_COLUMNS = (
    COMPARISON_KEYS + ["policy"] + PAIRED_METRICS + [f"fcfs_{column}" for column in PAIRED_METRICS]
    + [f"paired_{column}_difference" for column in PAIRED_METRICS]
)
SUMMARY_GROUP_COLUMNS = [
    "policy", "budget_fraction", "demand_imbalance", "estimator_noise_sigma", "routing_eligibility",
    "reservation_multiplier", "reservation_mode", "reservation_quantile", "output_cap", "model_output_caps",
    "routed_output_length_multiplier",
]
SUMMARY_METRICS = [
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
PAIRED_SUMMARY_METRICS = [
    "paired_completed_total_difference", "paired_realized_cost_micro_usd_difference",
    "paired_min_tenant_completion_rate_difference", "paired_budget_utilization_difference",
]
SUMMARY_COLUMNS = SUMMARY_GROUP_COLUMNS + ["replicates"] + [
    column
    for metric in SUMMARY_METRICS
    for column in (f"mean_{metric}", f"ci95_low_{metric}", f"ci95_high_{metric}")
] + [
    column
    for metric in PAIRED_SUMMARY_METRICS
    for column in (
        f"mean_{metric}", f"ci95_low_{metric}", f"ci95_high_{metric}", f"win_rate_{metric}", f"effect_size_{metric}"
    )
]
REGIME_COLUMNS = [
    "policy", "budget_fraction", "imbalance_regime", "uncertainty_regime", "completion_advantage_over_fcfs",
    "min_tenant_rate_advantage_over_fcfs", "budget_utilization_advantage_over_fcfs",
]


def _with_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=columns)
    return frame.reindex(columns=columns)


def write_outputs(results: ExperimentResults, output_dir: str | Path) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    tables = {
        "event_traces.parquet": (_with_columns(results.event_traces, TRACE_COLUMNS), True),
        "budget_timeseries.parquet": (_with_columns(results.budget_timeseries, TIMESERIES_COLUMNS), True),
        "run_metrics.csv": (_with_columns(results.run_metrics, RUN_META_COLUMNS + METRIC_COLUMNS), False),
        "tenant_metrics.csv": (_with_columns(results.tenant_metrics, TENANT_META_COLUMNS), False),
        "experiment_summary.csv": (_with_columns(results.experiment_summary, SUMMARY_COLUMNS), False),
        "policy_comparisons.csv": (_with_columns(results.policy_comparisons, COMPARISON_COLUMNS), False),
        "regime_map.csv": (_with_columns(results.regime_map, REGIME_COLUMNS), False),
    }
    for filename, (frame, parquet) in tables.items():
        path = destination / filename
        if parquet:
            if filename == "event_traces.parquet" and "modeled_routed_output_tokens" in frame:
                frame["modeled_routed_output_tokens"] = pd.array(
                    frame["modeled_routed_output_tokens"], dtype="Int64"
                )
            frame.to_parquet(path, index=False)
        else:
            frame.to_csv(path, index=False)
        paths.append(path)

    metadata_path = destination / "scenario_metadata.json"
    metadata_path.write_text(json.dumps(results.scenario_metadata, indent=2, default=str), encoding="utf-8")
    paths.append(metadata_path)
    findings_path = destination / "findings.md"
    findings_path.write_text(
        generate_findings(results.experiment_summary, results.policy_comparisons, results.scenario_metadata),
        encoding="utf-8",
    )
    paths.append(findings_path)
    paths.extend(write_diagnostics(results, destination))
    return paths


def generate_findings(summary: pd.DataFrame, comparisons: pd.DataFrame, metadata: Mapping[str, Any]) -> str:
    label = str(metadata.get("data_label", "USER-PROVIDED INPUT"))
    lines = [
        "# Simulation Findings",
        "",
        f"Dataset label: **{label}**. All budgets and routed outcomes are modeled/counterfactual.",
        "No result is a claim about request quality or equivalence between models.",
        "",
        "Intervals describe workload resampling and modeled assumptions only; they are not real-world cost uncertainty.",
        "",
        "## Pre-registered hypotheses",
    ]
    if summary.empty:
        lines.extend(["", "Inconclusive: no experiment summary rows are available."])
        return "\n".join(lines) + "\n"

    means = summary.groupby("policy", dropna=False).agg(
        completed=("mean_completed_total", "mean"),
        minimum=("mean_min_tenant_completion_rate", "mean"),
        cost=("mean_realized_cost_micro_usd", "mean"),
    )
    def verdict(value: bool | None, detail: str) -> str:
        status = "SUPPORTED" if value is True else "NOT SUPPORTED" if value is False else "INCONCLUSIVE"
        return f"- {status}: {detail}"

    fcfs = means.loc["FCFS"] if "FCFS" in means.index else None
    quotas = means.loc["Quotas"] if "Quotas" in means.index else None
    adaptive = means.loc["Adaptive"] if "Adaptive" in means.index else None
    pacing = means.loc["Pacing"] if "Pacing" in means.index else None
    threshold = means.loc["Threshold"] if "Threshold" in means.index else None
    lines.append("")
    if fcfs is not None and quotas is not None:
        lines.append(verdict(
            fcfs["completed"] >= quotas["completed"] and fcfs["minimum"] <= quotas["minimum"],
            f"H1 aggregate/minimum-tenant direction: FCFS={fcfs['completed']:.2f}/{fcfs['minimum']:.3f}; "
            f"Quotas={quotas['completed']:.2f}/{quotas['minimum']:.3f}.",
        ))
    else:
        lines.append(verdict(None, "H1 requires FCFS and Quotas results."))
    if fcfs is not None and quotas is not None and adaptive is not None:
        recovered = adaptive["completed"] >= quotas["completed"] and adaptive["minimum"] >= quotas["minimum"]
        lines.append(verdict(recovered, "H2 adaptive sharing recovers quota completions while retaining the floor."))
    else:
        lines.append(verdict(None, "H2 requires FCFS, Quotas, and Adaptive results."))
    if adaptive is not None and pacing is not None and threshold is not None:
        lines.append(verdict(
            threshold["completed"] >= adaptive["completed"] and threshold["completed"] >= pacing["completed"],
            f"H3 threshold completions={threshold['completed']:.2f}, adaptive={adaptive['completed']:.2f}, "
            f"pacing={pacing['completed']:.2f}.",
        ))
    else:
        lines.append(verdict(None, "H3 requires Threshold, Adaptive, and Pacing results."))

    eligibility_values = summary["routing_eligibility"].dropna().unique() if "routing_eligibility" in summary else []
    output_values = summary["routed_output_length_multiplier"].dropna().unique() if "routed_output_length_multiplier" in summary else []
    if len(eligibility_values) > 1 and len(output_values) > 1:
        lines.append(verdict(None, "H4 is evaluated by the routing sensitivity outputs; inspect routing_sensitivity.png and the summary grid."))
    else:
        lines.append(verdict(None, "H4 inconclusive: eligibility and output-length multiplier were not both varied."))
    if summary["reservation_multiplier"].nunique() > 1:
        lines.append(verdict(None, "H5 reservation factors were varied; compare truncation and rejection in experiment_summary.csv."))
    else:
        lines.append(verdict(None, "H5 inconclusive: reservation multiplier was not varied."))

    lines.extend([
        "",
        "## Interpretation limits",
        "",
        "These results compare modeled request counts, costs, budget use, and tenant completion rates. "
        "Routed completions are counterfactual and are kept separate from original-model completions. "
        "Synthetic fixtures are SYNTHETIC TEST DATA, not CMU observations or real prices.",
    ])
    return "\n".join(lines) + "\n"


def write_diagnostics(results: ExperimentResults, output_dir: str | Path) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    summary = results.experiment_summary

    fig, axis = plt.subplots(figsize=(8, 5))
    if not summary.empty:
        plot = summary.groupby(["policy", "budget_fraction"], as_index=False)["mean_completed_total"].mean()
        for policy, group in plot.groupby("policy"):
            axis.plot(group["budget_fraction"], group["mean_completed_total"], marker="o", label=policy)
        axis.legend(fontsize=7)
    else:
        axis.text(0.5, 0.5, "No run metrics", ha="center", va="center")
    axis.set(xlabel="Modeled budget fraction", ylabel="Mean completed requests", title="Completion vs budget fraction")
    fig.tight_layout()
    paths.append(_save(fig, destination / "completion_vs_budget_fraction.png"))

    fig, axis = plt.subplots(figsize=(9, 5))
    if not results.tenant_metrics.empty:
        selected = results.tenant_metrics.groupby(["policy", "tenant"], as_index=False)["completion_rate_total"].mean()
        for policy, group in selected.groupby("policy"):
            axis.plot(group["tenant"], group["completion_rate_total"], marker="o", label=policy)
        axis.legend(fontsize=7)
    else:
        axis.text(0.5, 0.5, "No tenant metrics", ha="center", va="center")
    axis.set(xlabel="Billing/project group", ylabel="Mean completion rate", title="Per-tenant completion")
    fig.tight_layout()
    paths.append(_save(fig, destination / "per_tenant_completion.png"))

    fig, axis = plt.subplots(figsize=(9, 5))
    if not results.budget_timeseries.empty:
        first_scenario = results.budget_timeseries["scenario_id"].iloc[0]
        selected = results.budget_timeseries[results.budget_timeseries["scenario_id"] == first_scenario]
        for policy, group in selected.groupby("policy"):
            axis.step(range(len(group)), group["global_remaining_micro_usd"], where="post", label=policy)
        axis.legend(fontsize=7)
    else:
        axis.text(0.5, 0.5, "No timeseries rows", ha="center", va="center")
    axis.set(xlabel="Downsampled event index", ylabel="Modeled budget remaining (micro-USD)", title="Budget remaining over time")
    fig.tight_layout()
    paths.append(_save(fig, destination / "budget_remaining_over_time.png"))

    fig, axis = plt.subplots(figsize=(9, 5))
    if not summary.empty:
        paired = summary[summary["policy"] != "FCFS"]
        plotted = paired.groupby("policy", as_index=False).agg(
            mean=("mean_paired_completed_total_difference", "mean"),
            low=("ci95_low_paired_completed_total_difference", "mean"),
            high=("ci95_high_paired_completed_total_difference", "mean"),
        )
        if not plotted.empty:
            center = plotted["mean"].to_numpy(dtype=float)
            low = center - plotted["low"].to_numpy(dtype=float)
            high = plotted["high"].to_numpy(dtype=float) - center
            axis.errorbar(plotted["policy"], center, yerr=np.vstack([low, high]), fmt="o", capsize=3)
            axis.axhline(0, color="black", linewidth=0.8)
    axis.set(xlabel="Policy", ylabel="Paired completed-request difference vs FCFS", title="Paired differences with percentile intervals")
    axis.tick_params(axis="x", labelrotation=25)
    fig.tight_layout()
    paths.append(_save(fig, destination / "paired_differences_ci.png"))

    fig, axis = plt.subplots(figsize=(8, 5))
    if not summary.empty and "routing_eligibility" in summary:
        routed = summary[summary["policy"].str.contains("Routing", na=False)]
        if routed.empty:
            axis.text(0.5, 0.5, "No routed policies in this run", ha="center", va="center")
        else:
            for policy, group in routed.groupby("policy"):
                curve = group.groupby("routing_eligibility", as_index=False)["mean_completed_total"].mean()
                axis.plot(curve["routing_eligibility"], curve["mean_completed_total"], marker="o", label=policy)
            axis.legend(fontsize=7)
    else:
        axis.text(0.5, 0.5, "No routing sensitivity rows", ha="center", va="center")
    axis.set(xlabel="Modeled routing eligibility probability", ylabel="Mean completed requests", title="Routing sensitivity")
    fig.tight_layout()
    paths.append(_save(fig, destination / "routing_sensitivity.png"))
    return paths


def _save(figure: Any, path: Path) -> Path:
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path
