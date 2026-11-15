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

# ---- simulation (curated canonical results)
P = f"{RES}/canonical/policies"
runs = pd.read_csv(f"{P}/run_metrics.csv")
tenants = pd.read_csv(f"{P}/tenant_metrics.csv")
traj = pd.read_csv(f"{P}/budget_trajectories.csv")
traj["day"] = (pd.to_datetime(traj.timestamp, format="ISO8601") - pd.Timestamp("2026-10-01", tz="UTC")).dt.total_seconds() / 86400 + 1
POL = ["FCFS", "Quotas", "TrainingQuotas", "Adaptive", "Pacing", "Threshold"]
cells = {}
for p in POL:
    for b in [100, 85, 70, 50]:
        r = runs[(runs.policy == p) & (runs.budget_fraction.round(2) == b / 100)]
        assert len(r) == 1, (p, b)
        r = r.iloc[0]
        t = tenants[tenants.run_id == r.run_id].set_index("tenant").loc[TEAMS]
        tr = traj[traj.run_id == r.run_id].sort_values("day")
        cells[f"{p}_{b}"] = {
            "done": int(r.completed_original), "rate": round(100 * r.completion_rate_original, 2),
            "trunc": int(r.truncated), "rej": int(r.rejected), "n": int(r.request_count),
            "left": round(100 * r.budget_remaining_fraction, 2), "leftUsd": round(r.budget_remaining_micro_usd / 1e6, 2),
            "teams": (100 * t.completion_rate_original).round(2).tolist(),
            "teamsDone": t.completed_original.astype(int).tolist(),
            "trace": [[round(d, 3), round(100 * v / r.budget_micro_usd, 2)] for d, v in zip(tr.day, tr.global_remaining_micro_usd)]}
D["cells"] = cells
D["sim"] = {"n": int(runs.request_count.iloc[0]), "refUsd": round(runs.reference_cost_micro_usd.iloc[0] / 1e6)}
open(OUT, "w").write(open(TPL).read().replace("/*__DATA__*/null", json.dumps(D)))
print("ok", OUT)
