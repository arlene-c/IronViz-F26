"""Build descriptive charts for the corrected October Monte Carlo study.

The script reads only the saved study tables in ``../monte_carlo``. It does not
run the simulator. All intervals describe empirical resample spread; they are
not confidence intervals.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


PRESENTATION = Path(__file__).resolve().parents[1]
SOURCE = PRESENTATION / "monte_carlo"
OUT = Path(__file__).resolve().parent

INK = "#171717"
MUTED = "#5f6368"
GRID = "#d9d9d4"
COLORS = {
    "FCFS": "#6d7378",
    "Quotas": "#2b9cca",
    "TrainingQuotas": "#7652b5",
    "Adaptive": "#188a7a",
    "Pacing": "#729d25",
    "Threshold": "#cf4779",
}
MARKERS = {
    "FCFS": "o",
    "Quotas": "s",
    "TrainingQuotas": "v",
    "Adaptive": "^",
    "Pacing": "D",
    "Threshold": "P",
}
ORDER = ["FCFS", "Quotas", "TrainingQuotas", "Adaptive", "Pacing", "Threshold"]
NAMES = {
    "FCFS": "First come, first served",
    "Quotas": "Equal quotas",
    "TrainingQuotas": "Training-week quotas",
    "Adaptive": "Adaptive sharing",
    "Pacing": "Spend pacing",
    "Threshold": "Cost threshold",
}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10.5,
            "axes.edgecolor": "#a4a6a1",
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": MUTED,
            "xtick.color": MUTED,
            "ytick.color": INK,
            "text.color": INK,
            "figure.facecolor": "#ffffff",
            "axes.facecolor": "#ffffff",
            "svg.fonttype": "none",
        }
    )


def add_title(fig: plt.Figure, title: str, subtitle: str) -> None:
    fig.text(0.01, 0.965, title, fontsize=16, fontweight="medium", va="top")
    fig.text(0.01, 0.905, subtitle, fontsize=10.5, color=MUTED, va="top")


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def read_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    runs = pd.read_csv(SOURCE / "replicate_results.csv")
    effects = pd.read_csv(SOURCE / "paired_effects.csv").set_index("policy")
    summary = pd.read_csv(SOURCE / "policy_summary.csv").set_index("policy")
    assert len(runs) == 300
    assert runs.groupby("replicate").size().eq(6).all()
    assert not runs.duplicated(["replicate", "policy"]).any()
    assert (runs.completed_original + runs.rejected + runs.truncated == runs.request_count).all()
    assert effects.resamples.eq(49).all()
    for policy, group in runs[runs.replicate > 0].groupby("policy"):
        assert len(group) == 49
        assert np.isclose(group.completion_difference_pp.median(), effects.loc[policy, "median_difference_pp"])
    return runs, effects, summary


def effect_distribution(runs: pd.DataFrame, effects: pd.DataFrame) -> None:
    policies = [policy for policy in ORDER if policy != "FCFS"]
    fig, ax = plt.subplots(figsize=(11.5, 7.1))
    add_title(
        fig,
        "Completion effects remain ordered across 49 paired workload resamples",
        "Change in fully completed requests versus first come, first served (percentage points). "
        "Thick bars show the resample IQR; they are outcome spread, not confidence intervals.",
    )
    rng = np.random.default_rng(20261115)
    y_positions = {policy: len(policies) - 1 - index for index, policy in enumerate(policies)}
    xmax = float(runs.completion_difference_pp.max()) + 1.8
    xmin = min(-1.8, float(runs.completion_difference_pp.min()) - 0.8)
    for policy in policies:
        group = runs[(runs.replicate > 0) & (runs.policy == policy)]
        effect = effects.loc[policy]
        y0 = y_positions[policy]
        y = y0 + rng.uniform(-0.18, 0.18, len(group))
        ax.scatter(
            group.completion_difference_pp,
            y,
            s=30,
            marker=MARKERS[policy],
            color=COLORS[policy],
            alpha=0.68,
            linewidths=0,
            zorder=3,
        )
        ax.plot(
            [effect.q25_difference_pp, effect.q75_difference_pp],
            [y0, y0],
            color=COLORS[policy],
            lw=7,
            solid_capstyle="round",
            zorder=4,
        )
        ax.scatter([effect.median_difference_pp], [y0], s=78, marker="D", color=INK, edgecolor="white", linewidth=1.1, zorder=5)
        replay = runs[(runs.replicate == 0) & (runs.policy == policy)].completion_difference_pp.iloc[0]
        ax.scatter([replay], [y0], s=84, marker="^", color="white", edgecolor=COLORS[policy], linewidth=1.7, zorder=6)
        ax.text(xmax - 0.05, y0 + 0.22, f"median {effect.median_difference_pp:+.2f} pp", va="center", ha="right", fontsize=10, fontweight="medium")
    ax.axvline(0, color=INK, lw=1.1, zorder=1)
    ax.text(0, len(policies) - 0.42, "same completion rate as FCFS", ha="center", va="bottom", fontsize=9.5, color=MUTED)
    ax.set_xlim(xmin, xmax + 0.1)
    ax.set_ylim(-0.62, len(policies) - 0.02)
    ax.set_yticks([y_positions[policy] for policy in policies], [NAMES[policy] for policy in policies])
    ax.set_xlabel("Completion-rate difference from FCFS (percentage points)")
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(
        handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor=INK, markersize=6, label="one resample"),
            Line2D([0], [0], marker="D", color="none", markerfacecolor=INK, markersize=7, label="resample median"),
            Line2D([0], [0], marker="^", color="none", markerfacecolor="white", markeredgecolor=INK, markersize=7, label="separate replay"),
            Line2D([0, 1], [0, 0], color=INK, lw=6, label="resample IQR"),
        ],
        loc="lower left",
        bbox_to_anchor=(0, 1.005),
        ncol=4,
        frameon=False,
        fontsize=9.5,
        handlelength=1.5,
    )
    fig.subplots_adjust(left=0.19, right=0.98, top=0.80, bottom=0.12)
    save(fig, "12_monte_carlo_effect_distribution_2D")


def replay_vs_resamples(runs: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 7.2))
    add_title(
        fig,
        "The original replay tracks the resample distributions",
        "Fully completed requests (%). Dots are 49 local-block resamples; thick bars are IQRs; triangles are the separate replay.",
    )
    rng = np.random.default_rng(20261116)
    y_positions = {policy: len(ORDER) - 1 - index for index, policy in enumerate(ORDER)}
    for policy in ORDER:
        group = runs[(runs.replicate > 0) & (runs.policy == policy)]
        series = group.completion_pct
        y0 = y_positions[policy]
        ax.scatter(series, y0 + rng.uniform(-0.18, 0.18, len(series)), s=30, marker=MARKERS[policy], color=COLORS[policy], alpha=0.68, linewidths=0, zorder=3)
        ax.plot([series.quantile(.25), series.quantile(.75)], [y0, y0], color=COLORS[policy], lw=7, solid_capstyle="round", zorder=4)
        ax.scatter([series.median()], [y0], s=78, marker="D", color=INK, edgecolor="white", linewidth=1.1, zorder=5)
        replay = runs[(runs.replicate == 0) & (runs.policy == policy)].completion_pct.iloc[0]
        ax.scatter([replay], [y0], s=84, marker="^", color="white", edgecolor=COLORS[policy], linewidth=1.7, zorder=6)
    ax.set_xlim(31, 50.5)
    ax.set_ylim(-0.62, len(ORDER) - 0.02)
    ax.set_yticks([y_positions[policy] for policy in ORDER], [NAMES[policy] for policy in ORDER])
    ax.set_xlabel("Fully completed requests (%)")
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(
        handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor=INK, markersize=6, label="one resample"),
            Line2D([0], [0], marker="D", color="none", markerfacecolor=INK, markersize=7, label="resample median"),
            Line2D([0], [0], marker="^", color="none", markerfacecolor="white", markeredgecolor=INK, markersize=7, label="original replay"),
            Line2D([0, 1], [0, 0], color=INK, lw=6, label="resample IQR"),
        ],
        loc="lower left",
        bbox_to_anchor=(0, 1.005),
        ncol=4,
        frameon=False,
        fontsize=9.5,
        handlelength=1.5,
    )
    fig.subplots_adjust(left=0.19, right=0.98, top=0.80, bottom=0.12)
    save(fig, "13_monte_carlo_replay_vs_resamples_2D")


def access_floor_scatter(runs: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 6.5))
    add_title(
        fig,
        "More completions do not automatically protect the lowest-served team",
        "Each mark is one of 49 local-block synthetic resamples per policy. Tenant groups are operational, not demographic.",
    )
    resamples = runs[runs.replicate > 0]
    for policy in ORDER:
        group = resamples[resamples.policy == policy]
        ax.scatter(group.completion_pct, group.min_tenant_completion_pct, s=35, marker=MARKERS[policy], color=COLORS[policy], alpha=0.5, linewidths=0, label=NAMES[policy], zorder=3)
        x = summary.loc[policy, "median_completion_pct"]
        y = summary.loc[policy, "median_min_tenant_completion_pct"]
        ax.scatter([x], [y], s=118, marker="D", color=COLORS[policy], edgecolor="white", linewidth=1.3, zorder=5)
    ax.set_xlim(31, 50.5)
    ax.set_ylim(14, 50)
    ax.set_xlabel("Fully completed requests (%)")
    ax.set_ylabel("Lowest operational-tenant completion rate (%)")
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", frameon=False, fontsize=8.8, ncol=2)
    fig.subplots_adjust(left=0.13, right=0.98, top=0.80, bottom=0.13)
    save(fig, "14_monte_carlo_access_floor_2D")


def write_alt_text() -> None:
    (OUT / "ALT_TEXT.txt").write_text(
        "12_monte_carlo_effect_distribution_2D\n"
        "A five-row dot-and-interval plot of 49 paired resample effects versus first come, first served. Median completion-rate changes are +0.26 percentage points for equal quotas, +3.93 for training-week quotas, +4.87 for adaptive sharing, +10.16 for spend pacing, and +12.30 for the cost threshold. Equal quotas is above FCFS in 31 of 49 resamples; all other non-FCFS policies are above FCFS in all 49.\n\n"
        "13_monte_carlo_replay_vs_resamples_2D\n"
        "A six-row dot-and-interval plot of completion rates over 49 resamples. The policies retain the same broad ordering in the replay and resample distributions: equal quotas and FCFS are near 35%, training-week quotas near 39%, adaptive sharing near 40%, spend pacing near 45%, and the cost threshold near 48%.\n\n"
        "14_monte_carlo_access_floor_2D\n"
        "Scatter plot of overall completion against the lowest operational-tenant completion rate. Cost threshold and spend pacing appear in the upper right. Adaptive sharing has higher overall completion than FCFS but a lower median access floor. Equal quotas has the lowest access floor despite an overall completion rate similar to FCFS.\n",
        encoding="utf-8",
    )


def main() -> None:
    configure_style()
    runs, effects, summary = read_tables()
    effect_distribution(runs, effects)
    replay_vs_resamples(runs)
    access_floor_scatter(runs, summary)
    write_alt_text()
    print(f"Created three charts from {len(runs)} policy runs in {OUT}")


if __name__ == "__main__":
    main()
