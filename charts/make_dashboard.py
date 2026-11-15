"""Build the one-page interactive dashboard from the curated simulation results.
Usage: python charts/make_dashboard.py results charts/dashboard_template.html figures/dashboard.html

Simulation numbers come from results/canonical/policies (six policies x four budgets, one replay each).
Descriptive "real data" panels come from results/analysis_*.csv."""
import sys, json
import pandas as pd

RES, TPL, OUT = sys.argv[1:4]
POLDIR = f"{RES}/canonical/policies"
runs = pd.read_csv(f"{POLDIR}/run_metrics.csv")
tenants = pd.read_csv(f"{POLDIR}/tenant_metrics.csv")
traj = pd.read_csv(f"{POLDIR}/budget_trajectories.csv")
team = pd.read_csv(f"{RES}/analysis_team_summary.csv")
model = pd.read_csv(f"{RES}/analysis_cost_by_model.csv")
week = pd.read_csv(f"{RES}/analysis_weekly_trend.csv")

TEAMS = ["org-prod-core", "org-marketing-ai", "org-engineering-dev",
         "prj-ai-enterprise-prod", "prj-ai-r-and-d", "prj-ai-sandbox-testing"]
POL = ["FCFS", "Quotas", "TrainingQuotas", "Adaptive", "Pacing", "Threshold"]
BUD = [100, 85, 70, 50]
OCT1 = pd.Timestamp("2026-10-01", tz="UTC")
traj["day"] = (pd.to_datetime(traj.timestamp, format="ISO8601") - OCT1).dt.total_seconds() / 86400 + 1

cells = {}
for p in POL:
    for b in BUD:
        r = runs[(runs.policy == p) & (runs.budget_fraction.round(2) == b / 100)]
        assert len(r) == 1, (p, b, len(r))
        r = r.iloc[0]
        n = int(r.request_count)
        tm = tenants[tenants.run_id == r.run_id].set_index("tenant").loc[TEAMS]
        tr = traj[traj.run_id == r.run_id].sort_values("day")
        cells[f"{p}_{b}"] = {
            "done": int(r.completed_original),
            "doneRate": round(100 * r.completion_rate_original, 2),
            "trunc": int(r.truncated), "rej": int(r.rejected), "n": n,
            "left": round(100 * r.budget_remaining_fraction, 2),
            "leftUsd": round(r.budget_remaining_micro_usd / 1e6, 2),
            "gap": round(100 * r.max_min_completion_gap, 2),
            "teams": (100 * tm.completion_rate_original).round(2).tolist(),
            "teamsDone": tm.completed_original.astype(int).tolist(),
            "trace": [[round(d, 3), round(100 * v / r.budget_micro_usd, 2)]
                      for d, v in zip(tr.day, tr.global_remaining_micro_usd)],
        }

tm = team.set_index("tenant").loc[TEAMS]
wk_order = sorted(week.week.unique(), key=lambda w: int(w.split()[1].split("-")[0]))
week["wk_i"] = week.week.map(wk_order.index)
ref = runs.iloc[0]
D = {
    "cells": cells, "teams": TEAMS, "provider": tm.provider.tolist(),
    "testing": tm.testing_team.astype(bool).tolist(),
    "kpi": {"testCalls": round(tm[tm.testing_team].call_share_pct.sum()),
            "testTokens": round(tm[tm.testing_team].token_share_pct.sum())},
    "evalN": int(ref.request_count), "refUsd": round(ref.reference_cost_micro_usd / 1e6, 2),
    "models": model[["model", "call_share_pct", "cost_share_pct"]].round(1).values.tolist(),
    "weeks": wk_order,
    "weekly": {t: {"cache": week[week.tenant == t].sort_values("wk_i").calls_using_cache_pct.round(1).tolist(),
                   "prem": week[week.tenant == t].sort_values("wk_i").premium_model_pct.round(1).tolist()}
               for t in TEAMS},
}
open(OUT, "w").write(open(TPL).read().replace("/*__DATA__*/null", json.dumps(D)))
print("ok", OUT)
