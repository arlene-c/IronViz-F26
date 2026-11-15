"""Build the click-through data story.
Usage: python charts/make_story.py results charts/story_template.html figures/story.html

Chapters 1-3 use the descriptive telemetry summaries (real data).
Chapters 4-7 use the curated simulation in results/canonical/policies
(six policies x four budgets, one replay each, pre-correction)."""
import sys, json
import pandas as pd

RES, TPL, OUT = sys.argv[1:4]
team = pd.read_csv(f"{RES}/analysis_team_summary.csv").set_index("tenant")
model = pd.read_csv(f"{RES}/analysis_cost_by_model.csv")
week = pd.read_csv(f"{RES}/analysis_weekly_trend.csv")
s = json.load(open(f"{RES}/settings.json"))
C = pd.read_csv(f"{RES}/clean_requests.csv", usecols=["tenant", "status", "input_tokens", "output_tokens", "exclude_reason"], low_memory=False)
ok = C[C.exclude_reason.isna()]

TEAMS = ["org-prod-core", "prj-ai-enterprise-prod", "org-marketing-ai", "prj-ai-r-and-d", "org-engineering-dev", "prj-ai-sandbox-testing"]
PERSONA = {"org-prod-core": "prod", "prj-ai-enterprise-prod": "prod", "org-marketing-ai": "learn", "prj-ai-r-and-d": "learn",
           "org-engineering-dev": "exp", "prj-ai-sandbox-testing": "exp"}
wk = lambda w: int(str(w).split()[1].split("-")[0])
tm = team.loc[TEAMS]
D = {"teams": TEAMS, "persona": [PERSONA[t] for t in TEAMS], "provider": tm.provider.tolist(),
     "stats": {t: {"cache": round(tm.loc[t, "calls_using_cache_pct"], 1), "prem": round(tm.loc[t, "premium_model_pct"], 1),
                   "prompt": int(tm.loc[t, "median_prompt_tokens"]), "bad": round(tm.loc[t, "bad_request_pct"], 1),
                   "cost": round(tm.loc[t, "cost_share_pct"], 1), "calls": round(tm.loc[t, "call_share_pct"], 1),
                   "tokens": round(tm.loc[t, "token_share_pct"], 1)} for t in TEAMS},
     "kpi": {"calls": int(len(C)), "success": round((C.status == 200).mean() * 100, 1), "cost": round(s["baseline_october_cost_usd"]),
             "n400": int((C.status == 400).sum()), "n429": int((C.status == 429).sum()),
             "testCalls": round(tm[tm.testing_team].call_share_pct.sum()), "testTokens": round(tm[tm.testing_team].token_share_pct.sum())},
     "models": model.sort_values("cost_share_pct", ascending=False)[["model", "call_share_pct", "cost_share_pct"]].round(1).values.tolist(),
     "weekly": {t: {k: week[week.tenant == t].assign(o=lambda d: d.week.map(wk)).sort_values("o")[c].round(1).tolist()
                    for k, c in [("cache", "calls_using_cache_pct"), ("prem", "premium_model_pct")]} for t in TEAMS},
     "weeks": sorted(week.week.unique(), key=wk),
     "strip": {t: {"pts": [int(v) for v in ok[ok.tenant == t].input_tokens.sample(110, random_state=4)],
                   "med": int(ok[ok.tenant == t].input_tokens.median())} for t in TEAMS}}

# ---- simulation: results/presentation is the primary source (chart-ready, from main).
# Budget curves and tenant rates at budgets other than 70% exist only in results/canonical;
# they are joined on the saved run id (presentation source_run_id == canonical run_id).
PRES, CAN = f"{RES}/presentation", f"{RES}/canonical/policies"
pb = pd.read_csv(f"{PRES}/policy_budget_summary.csv")
tt = pd.read_csv(f"{PRES}/tenant_tradeoffs_70pct.csv")
tenants = pd.read_csv(f"{CAN}/tenant_metrics.csv")
traj = pd.read_csv(f"{CAN}/budget_trajectories.csv")
traj["day"] = (pd.to_datetime(traj.timestamp, format="ISO8601") - pd.Timestamp("2026-10-01", tz="UTC")).dt.total_seconds() / 86400 + 1
POL = ["FCFS", "Quotas", "TrainingQuotas", "Adaptive", "Pacing", "Threshold"]
cells = {}
for p in POL:
    for b in [100, 85, 70, 50]:
        r = pb[(pb.policy == p) & (pb.budget_pct == b)]
        assert len(r) == 1, (p, b)
        r = r.iloc[0]
        if b == 70:
            t = tt[tt.policy == p].set_index("tenant").loc[TEAMS]
            t_rate, t_done = t.completion_pct, t.completed_requests
        else:
            t = tenants[tenants.run_id == r.source_run_id].set_index("tenant").loc[TEAMS]
            t_rate, t_done = 100 * t.completion_rate_original, t.completed_original
        tr = traj[traj.run_id == r.source_run_id].sort_values("day")
        assert len(tr), (p, b, "no trajectory")
        cells[f"{p}_{b}"] = {
            "done": int(r.completed_requests), "rate": round(r.completion_pct, 2),
            "trunc": int(r.truncated_requests), "rej": int(r.rejected_requests), "n": int(r.request_count),
            "left": round(100 - r.budget_utilization_pct, 2), "leftUsd": round(r.unused_budget_usd, 2),
            "teams": t_rate.round(2).tolist(), "teamsDone": t_done.astype(int).tolist(),
            "trace": [[round(d, 3), round(100 * v / (r.budget_usd * 1e6), 2)] for d, v in zip(tr.day, tr.global_remaining_micro_usd)]}
D["cells"] = cells
full = pb[(pb.policy == "FCFS") & (pb.budget_pct == 100)].iloc[0]
D["sim"] = {"n": int(full.request_count), "refUsd": round(full.budget_usd)}

# ---- corrected October Monte Carlo: 49 simulated months at a 70% budget
MC = f"{PRES}/monte_carlo"
pe = pd.read_csv(f"{MC}/paired_effects.csv").set_index("policy")
ps = pd.read_csv(f"{MC}/policy_summary.csv").set_index("policy")
rr = pd.read_csv(f"{MC}/replicate_results.csv"); res = rr[rr.replicate > 0]
D["mc"] = {"resamples": int(pe.resamples.max()), "n": int(res.request_count.median()), "budget": 70,
           "pol": {p: {"diffs": res[res.policy == p].sort_values("replicate").completion_difference_pp.round(3).tolist(),
                       "replay": round(float(pe.loc[p, "replay_difference_pp"]), 3), "med": float(pe.loc[p, "median_difference_pp"]),
                       "q25": float(pe.loc[p, "q25_difference_pp"]), "q75": float(pe.loc[p, "q75_difference_pp"]),
                       "wins": int(pe.loc[p, "wins"]), "ties": int(pe.loc[p, "ties"]), "losses": int(pe.loc[p, "losses"]),
                       "medRate": round(float(ps.loc[p, "median_completion_pct"]), 2), "medTrunc": round(float(ps.loc[p, "median_truncation_pct"]), 2)}
                   for p in POL}}
D["rows"] = {"total": s["rows_total"], "used": s["rows_used"]}
open(OUT, "w").write(open(TPL).read().replace("/*__DATA__*/null", json.dumps(D)))
print("ok", OUT)
