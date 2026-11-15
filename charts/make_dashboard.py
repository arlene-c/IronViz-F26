"""Build the one-page interactive dashboard from the curated simulation results.
Usage: python charts/make_dashboard.py results charts/dashboard_template.html figures/dashboard.html

Simulation numbers come from results/presentation (chart-ready); budget curves and non-70% tenant
rates come from results/canonical/policies, joined on the saved run id.
Descriptive "real data" panels come from results/analysis_*.csv."""
import sys, json
import pandas as pd

RES, TPL, OUT = sys.argv[1:4]
PRES, CAN = f"{RES}/presentation", f"{RES}/canonical/policies"
pb = pd.read_csv(f"{PRES}/policy_budget_summary.csv")      # primary policy results (main)
tt = pd.read_csv(f"{PRES}/tenant_tradeoffs_70pct.csv")     # primary tenant results at 70%
tenants = pd.read_csv(f"{CAN}/tenant_metrics.csv")         # tenant rates at other budgets
traj = pd.read_csv(f"{CAN}/budget_trajectories.csv")       # budget curves
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
        r = pb[(pb.policy == p) & (pb.budget_pct == b)]
        assert len(r) == 1, (p, b, len(r))
        r = r.iloc[0]
        if b == 70:
            t = tt[tt.policy == p].set_index("tenant").loc[TEAMS]
            t_rate, t_done = t.completion_pct, t.completed_requests
        else:
            t = tenants[tenants.run_id == r.source_run_id].set_index("tenant").loc[TEAMS]
            t_rate, t_done = 100 * t.completion_rate_original, t.completed_original
        tr = traj[traj.run_id == r.source_run_id].sort_values("day")
        cells[f"{p}_{b}"] = {
            "done": int(r.completed_requests), "doneRate": round(r.completion_pct, 2),
            "trunc": int(r.truncated_requests), "rej": int(r.rejected_requests), "n": int(r.request_count),
            "left": round(100 - r.budget_utilization_pct, 2), "leftUsd": round(r.unused_budget_usd, 2),
            "gap": round(r.tenant_completion_gap_pp, 2),
            "teams": t_rate.round(2).tolist(), "teamsDone": t_done.astype(int).tolist(),
            "trace": [[round(d, 3), round(100 * v / (r.budget_usd * 1e6), 2)]
                      for d, v in zip(tr.day, tr.global_remaining_micro_usd)],
        }

tm = team.set_index("tenant").loc[TEAMS]
wk_order = sorted(week.week.unique(), key=lambda w: int(w.split()[1].split("-")[0]))
week["wk_i"] = week.week.map(wk_order.index)
full = pb[(pb.policy == "FCFS") & (pb.budget_pct == 100)].iloc[0]
D = {
    "cells": cells, "teams": TEAMS, "provider": tm.provider.tolist(),
    "testing": tm.testing_team.astype(bool).tolist(),
    "kpi": {"testCalls": round(tm[tm.testing_team].call_share_pct.sum()),
            "testTokens": round(tm[tm.testing_team].token_share_pct.sum())},
    "evalN": int(full.request_count), "refUsd": round(full.budget_usd, 2),
    "models": model[["model", "call_share_pct", "cost_share_pct"]].round(1).values.tolist(),
    "weeks": wk_order,
    "weekly": {t: {"cache": week[week.tenant == t].sort_values("wk_i").calls_using_cache_pct.round(1).tolist(),
                   "prem": week[week.tenant == t].sort_values("wk_i").premium_model_pct.round(1).tolist()}
               for t in TEAMS},
}
# ---- corrected Monte Carlo: 49 simulated months at a 70% budget (ranges)
MC = f"{PRES}/monte_carlo"
pe = pd.read_csv(f"{MC}/paired_effects.csv").set_index("policy")
ps = pd.read_csv(f"{MC}/policy_summary.csv").set_index("policy")
rr = pd.read_csv(f"{MC}/replicate_results.csv"); rr = rr[rr.replicate > 0]
to = pd.read_csv(f"{MC}/tenant_outcomes.csv")
D["mc"] = {"months": int(pe.resamples.max()), "n": int(rr.request_count.median()), "pol": {}}
for p in POL:
    q = rr[rr.policy == p].completion_pct
    D["mc"]["pol"][p] = {"med": round(float(ps.loc[p, "median_completion_pct"]), 1),
        "lo": round(float(q.quantile(.05)), 1), "hi": round(float(q.quantile(.95)), 1),
        "dmed": round(float(pe.loc[p, "median_difference_pp"]), 1), "dlo": round(float(pe.loc[p, "p05_difference_pp"]), 1),
        "dhi": round(float(pe.loc[p, "p95_difference_pp"]), 1), "wins": int(pe.loc[p, "wins"]),
        "trunc": round(float(ps.loc[p, "median_truncation_pct"]), 1), "rej": round(float(ps.loc[p, "median_rejection_pct"]), 1),
        "teams": [round(float(to[(to.policy == p) & (to.tenant == t)].median_difference_pp.iloc[0]), 1) for t in TEAMS]}
st = json.load(open(f"{RES}/settings.json"))
ex = st["excluded"]
D["rows"] = {"total": st["rows_total"], "used": st["rows_used"],
             "n400": next(v for k, v in ex.items() if "400" in k), "n429": next(v for k, v in ex.items() if "429" in k),
             "bad": next(v for k, v in ex.items() if "negative" in k)}
D["cost"] = round(st["baseline_october_cost_usd"])
open(OUT, "w").write(open(TPL).read().replace("/*__DATA__*/null", json.dumps(D)))
print("ok", OUT)
