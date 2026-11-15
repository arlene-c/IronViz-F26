"""CMU IronViz Fall 2026: telemetry preparation and descriptive analysis.

Default execution performs NO simulations. Historical four-policy experiments
require the explicit --run-legacy-experiments flag and are not current results.

Requires: pandas, numpy.  Optional: numba (makes the simulation about 50x faster).

    python ironviz_experiments.py --openai openai_pipeline_telemetry_raw.csv \
        --gemini gemini_pipeline_telemetry_raw.csv --prices prices.csv --out results

Pricing CSV columns (USD per 1 million tokens):
    model, input_per_million, cached_input_per_million, output_per_million  [required]
    cheaper_model                                                           [optional: routing downgrade target]
    source                                                                  [optional: citation]

Writes to --out:
    clean_requests.csv      every original row, standardized, with exclude_reason ("" = used in simulation)
    excluded_rows.csv       only the rows left out, and why
    expected_output.csv     the estimate table the policies use
    requests_sim.csv        the 192,847 rows the simulation replays, with real_cost, expected_cost, token_bucket
    analysis_team_summary.csv   team fingerprints: calls, cost, median prompt, premium share, cache use, error rates
    analysis_cost_by_model.csv  calls and cost by provider x model (o1-preview's share of cost, etc.)
    analysis_weekly_trend.csv   per team per week: cache use, premium share, median prompt, cost per day
    analysis_rate_limits_daily.csv  rate-limited (429) and bad (400) calls per day per provider and team
    results.csv             Exp 1 + 3: one row per policy x budget x run (run 0 = real October)
    exp2_buckets.csv        Exp 2: % served per tenant x request-size bucket at 70% budget
    exp3_summary.csv        Exp 3: 5th / 50th / 95th percentiles
    exp4_shock.csv          Exp 4: noisy-neighbour shock
    trace.csv               budget remaining per day, real October
    settings.json           every setting, prices and data counts, for the documentation
    checks.txt              invariant checks that passed

Policies:
    fcfs       one shared pool; admit if the expected cost fits in what is left.
    quotas     each tenant gets a fixed share (by October spend, or even); no sharing.
    adaptive   quotas, plus a tenant may borrow other tenants' IDLE budget: whatever they hold beyond their
               pace for the rest of the month (their quota x share of month left).
    routing    one shared pool; when spending runs ahead of a straight-line monthly pace, or a request no longer
               fits, expensive models are downgraded to cheaper_model. Answer quality is NOT modelled.
Legacy experiments use EXPECTED admission cost and charge REALIZED cost. The first group estimate falls back to its current output; this historical implementation is not leakage-free or a strict reservation engine.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from numba import njit
except ImportError:
    def njit(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]
        return lambda f: f

MODELS = ("gpt-4o", "gpt-4o-mini", "o1-preview", "gemini-1.5-pro", "gemini-1.5-flash")
POLICIES = ("fcfs", "quotas", "adaptive", "routing")          # names the chart scripts expect
BUDGET_LEVELS = (100, 85, 70, 50)
BUCKETS = ("Small (<2k)", "Medium (2k-10k)", "Large (>10k)")
NDAYS = 30
MONTH_START = pd.Timestamp("2026-10-01", tz="UTC")


# ----------------------------------------------------------------------------------------- 1. clean
def _parse_usage(series, provider):
    """Defensive JSON parse. Missing/malformed payloads become NaN instead of stopping the run."""
    rows = []
    for raw in series:
        out = (np.nan, np.nan, np.nan, np.nan)
        if isinstance(raw, str) and raw:
            try:
                d = json.loads(raw)
                if provider == "openai":
                    out = (d.get("prompt_tokens"), d.get("completion_tokens"),
                           (d.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
                           (d.get("completion_tokens_details") or {}).get("reasoning_tokens", 0))
                else:
                    out = (d.get("promptTokenCount"), d.get("candidatesTokenCount"),
                           d.get("cachedContentTokenCount", 0), np.nan)
            except (TypeError, ValueError, AttributeError):
                pass
        rows.append(out)
    return pd.DataFrame(rows, columns=["input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens"])


def clean_telemetry(openai_path, gemini_path, strict=False):
    """Standardize both providers into one table. Every row is kept and labelled with exclude_reason,
    so nothing disappears silently. strict=True stops instead (useful if a new data release looks wrong)."""
    mappings = [
        (openai_path, "OpenAI", "openai", {"id": "request_id", "created_at": "timestamp", "model": "model",
         "organization_id": "tenant", "status_code": "status", "error": "error"}, "usage"),
        (gemini_path, "Gemini", "gemini", {"response_id": "request_id", "timestamp": "timestamp",
         "model_version": "model", "gcp_project_id": "tenant", "http_response_code": "status",
         "error_details": "error"}, "usageMetadata"),
    ]
    chunks = []
    for path, label, provider, renames, usage_col in mappings:
        raw = pd.read_csv(path, dtype={usage_col: "string"})
        frame = raw.rename(columns=renames)[list(renames.values())].reset_index(drop=True)
        frame = pd.concat([frame, _parse_usage(raw[usage_col], provider)], axis=1)
        frame["provider"] = label
        chunks.append(frame)
    df = pd.concat(chunks, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce", format="ISO8601")
    df["status"] = pd.to_numeric(df["status"], errors="coerce")
    df["success"] = df["status"].between(200, 299)
    for c in ("input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    reason = pd.Series("", index=df.index, dtype=object)
    def flag(mask, text):
        reason[mask & (reason == "")] = text
    flag(df.timestamp.isna() | df.request_id.isna() | df.tenant.isna() | df.model.isna(), "missing id/time/tenant/model")
    flag(df.request_id.duplicated(keep=False), "duplicate request_id")
    flag(~df.success, "failed call (HTTP " + df.status.astype("Int64").astype(str) + "): no usage, not billed")
    flag(df[["input_tokens", "output_tokens", "cached_tokens"]].isna().any(axis=1), "HTTP 200 but usage missing or malformed")
    flag((df[["input_tokens", "output_tokens", "cached_tokens"]] < 0).any(axis=1), "negative token count")
    flag(df.reasoning_tokens < 0, "negative reasoning_tokens (invalid record)")
    flag(df.cached_tokens > df.input_tokens, "cached tokens exceed input tokens")
    flag(~df.model.isin(MODELS), "unknown model (no price)")
    flag(df.timestamp >= MONTH_START + pd.Timedelta(days=NDAYS), "outside Oct 1-30 window")
    df["exclude_reason"] = reason

    data_errors = reason[(reason != "") & ~reason.str.startswith("failed call")]
    if strict and len(data_errors):
        raise ValueError(f"{len(data_errors)} invalid records:\n{data_errors.value_counts().to_string()}")
    return df.sort_values(["timestamp", "request_id"], kind="stable").reset_index(drop=True)


# ----------------------------------------------------------------------------------------- 2. prices
def read_prices(path):
    p = pd.read_csv(path, dtype={"cheaper_model": "string"})
    required = {"model", "input_per_million", "cached_input_per_million", "output_per_million"}
    if not required.issubset(p.columns):
        raise ValueError(f"Pricing CSV missing columns: {sorted(required - set(p.columns))}")
    if p.model.duplicated().any():
        raise ValueError("Pricing CSV has duplicate model entries")
    for c in required - {"model"}:
        p[c] = pd.to_numeric(p[c], errors="raise")
        if p[c].isna().any() or (p[c] < 0).any():
            raise ValueError(f"Missing or negative prices in {c}; fill every price cell")
    if (p.cached_input_per_million > p.input_per_million).any():
        raise ValueError("A cached price is higher than its input price; check the table")
    missing = set(MODELS) - set(p.model)
    if missing:
        raise ValueError(f"Missing prices for {sorted(missing)}")
    if "cheaper_model" not in p.columns:
        p["cheaper_model"] = ""
    p["cheaper_model"] = p.cheaper_model.fillna("").astype(str).str.strip().replace({"<NA>": "", "nan": ""}).astype(object)
    bad = set(p.cheaper_model) - set(p.model) - {""}
    if bad:
        raise ValueError(f"cheaper_model names a model with no price: {sorted(bad)}")
    return p.set_index("model")


def price(inp, cached, out, models, P):
    pr = P.loc[np.asarray(models)]
    return ((inp - cached) * pr.input_per_million.values + cached * pr.cached_input_per_million.values
            + out * pr.output_per_million.values) / 1e6


def expected_output(S, mode):
    """Output-token estimate the policies may use. 'online' = median of that tenant x model's EARLIER requests
    only (no look-ahead); 'month' = whole-month median (simpler, slight look-ahead)."""
    g = S.groupby(["tenant", "model"]).output_tokens
    if mode == "month":
        return g.transform("median").values
    prior = g.transform(lambda s: s.expanding().median().shift(1))
    return prior.fillna(g.transform("first")).values      # very first request of a group: use itself (1 row)


# ----------------------------------------------------------------------------------------- 3b. descriptive analysis
PREMIUM = {"gpt-4o", "o1-preview", "gemini-1.5-pro"}


def write_analysis(df, S, out):
    """The descriptive datasets behind the 'real data' charts (fingerprints, weekly trend, cost, rate limits)."""
    test = {"org-engineering-dev", "prj-ai-sandbox-testing"}
    S = S.assign(premium=S.model.isin(PREMIUM), cached_any=S.cached_tokens > 0,
                 tokens=S.input_tokens + S.output_tokens)
    allc = df[df.exclude_reason.isin(["", ]) | df.exclude_reason.str.startswith("failed call")]
    err = allc.groupby("tenant").status.agg(calls="size", bad_request_pct=lambda x: (x == 400).mean() * 100,
                                            rate_limited_pct=lambda x: (x == 429).mean() * 100)
    team = S.groupby("tenant").agg(provider=("provider", "first"), successful_calls=("request_id", "size"),
        cost_usd=("real_cost", "sum"), tokens=("tokens", "sum"), median_prompt_tokens=("input_tokens", "median"),
        premium_model_pct=("premium", lambda x: x.mean() * 100), calls_using_cache_pct=("cached_any", lambda x: x.mean() * 100),
        cached_share_of_input_pct=("cached_tokens", "sum"))
    team["cached_share_of_input_pct"] = team.cached_share_of_input_pct / S.groupby("tenant").input_tokens.sum() * 100
    team["cost_share_pct"] = team.cost_usd / team.cost_usd.sum() * 100
    team["token_share_pct"] = team.tokens / team.tokens.sum() * 100
    team = team.join(err); team["call_share_pct"] = team.calls / team.calls.sum() * 100
    team["testing_team"] = team.index.isin(test)
    team.round(2).reset_index().to_csv(out / "analysis_team_summary.csv", index=False)

    m = S.groupby(["provider", "model"]).agg(calls=("request_id", "size"), cost_usd=("real_cost", "sum"))
    m["call_share_pct"] = m.calls / m.calls.sum() * 100; m["cost_share_pct"] = m.cost_usd / m.cost_usd.sum() * 100
    m.round(2).reset_index().to_csv(out / "analysis_cost_by_model.csv", index=False)

    wk = pd.cut(S.timestamp.dt.day, [0, 7, 14, 21, 31], labels=["Oct 1-7", "Oct 8-14", "Oct 15-21", "Oct 22-30"])
    days = pd.Series({"Oct 1-7": 7, "Oct 8-14": 7, "Oct 15-21": 7, "Oct 22-30": 9})
    w = S.assign(week=wk).groupby(["tenant", "week"], observed=True).agg(calls=("request_id", "size"),
        calls_using_cache_pct=("cached_any", lambda x: x.mean() * 100), premium_model_pct=("premium", lambda x: x.mean() * 100),
        median_prompt_tokens=("input_tokens", "median"), cost_usd=("real_cost", "sum")).reset_index()
    w["cost_per_day_usd"] = w.cost_usd / w.week.astype(str).map(days)
    w["testing_team"] = w.tenant.isin(test)
    w.round(2).to_csv(out / "analysis_weekly_trend.csv", index=False)

    d = allc.assign(day=allc.timestamp.dt.day)
    rl = d.groupby(["day", "provider", "tenant"]).status.agg(rate_limited_429=lambda x: (x == 429).sum(),
                                                             bad_request_400=lambda x: (x == 400).sum(), calls="size")
    rl.reset_index().to_csv(out / "analysis_rate_limits_daily.csv", index=False)


# ----------------------------------------------------------------------------------------- 3. engine
@njit(cache=True)
def simulate(policy, budget, shares, tenant, tfrac, exp, real, exp_dn, real_dn, can_dn, ndays):
    n = tenant.shape[0]; T = shares.shape[0]
    admitted = np.zeros(n, np.bool_); downgraded = np.zeros(n, np.bool_); charged = np.zeros(n)
    spent_day = np.zeros(ndays); first_reject = -1.0
    pool = budget if (policy == 0 or policy == 3) else 0.0
    own = np.zeros(T)
    if policy == 1 or policy == 2:
        for k in range(T):
            own[k] = budget * shares[k]
    for i in range(n):
        t = tenant[i]; ok = False; ce = exp[i]; cr = real[i]
        if policy == 0:
            if ce <= pool:
                ok = True; pool -= cr
        elif policy == 1:
            if ce <= own[t]:
                ok = True; own[t] -= cr
        elif policy == 2:
            if ce <= own[t]:
                ok = True; own[t] -= cr
            else:
                left = 1.0 - tfrac[i]; idle = np.zeros(T); tot = 0.0
                for k in range(T):
                    if k != t:
                        v = own[k] - budget * shares[k] * left
                        if v > 0:
                            idle[k] = v; tot += v
                mine = own[t] if own[t] > 0 else 0.0
                if ce <= mine + tot:
                    ok = True; need = cr - mine; own[t] -= mine
                    if need > 0 and tot > 0:
                        for k in range(T):
                            own[k] -= need * idle[k] / tot
                    elif need > 0:
                        own[t] -= need
        else:
            ahead = (budget - pool) > budget * tfrac[i]
            if can_dn[i] and (ahead or ce > pool):
                ce = exp_dn[i]; cr = real_dn[i]
                if ce <= pool:
                    ok = True; downgraded[i] = True; pool -= cr
            elif ce <= pool:
                ok = True; pool -= cr
        if ok:
            admitted[i] = True; charged[i] = cr
            d = int(tfrac[i] * ndays)
            spent_day[d] += cr
        elif first_reject < 0:
            first_reject = tfrac[i] * ndays
    return admitted, downgraded, charged, spent_day, first_reject


class Arrays:
    """Per-request arrays for one workload, already priced (including the downgrade alternative)."""
    def __init__(self, S, P, est, teams):
        cheap = np.asarray(P.loc[S.model].cheaper_model.values, dtype=object)
        self.can_dn = np.asarray(cheap != "", dtype=np.bool_)
        dn_model = np.where(self.can_dn, cheap, S.model.values)
        i, c, o = S.input_tokens.values, S.cached_tokens.values, S.output_tokens.values
        self.real = price(i, c, o, S.model, P); self.exp = price(i, c, est, S.model, P)
        self.real_dn = price(i, c, o, dn_model, P); self.exp_dn = price(i, c, est, dn_model, P)
        self.tenant = S.tenant.map({t: k for k, t in enumerate(teams)}).values.astype(np.int64)
        self.bucket = pd.cut(S.input_tokens, [-1, 2000, 10000, np.inf], labels=False).values.astype(np.int64)
        secs = (S.timestamp - MONTH_START).dt.total_seconds().values
        self.tfrac = np.clip(secs / (NDAYS * 86400), 0, 0.999999)

    def take(self, idx, tfrac):
        return dict(tenant=self.tenant[idx], tfrac=tfrac, exp=self.exp[idx], real=self.real[idx],
                    exp_dn=self.exp_dn[idx], real_dn=self.real_dn[idx], can_dn=self.can_dn[idx])


def run(policy, budget, shares, w):
    return simulate(POLICIES.index(policy), budget, shares, w["tenant"], w["tfrac"], w["exp"], w["real"],
                    w["exp_dn"], w["real_dn"], w["can_dn"], NDAYS)


# ----------------------------------------------------------------------------------------- 4. experiments
def inject_demand_shock(S, target_tenant, start_date, end_date, multiplier):
    """Duplicate the target tenant's rows inside [start, end) so its volume becomes multiplier x normal."""
    w = (S.tenant == target_tenant) & (S.timestamp >= pd.Timestamp(start_date, tz="UTC")) \
        & (S.timestamp < pd.Timestamp(end_date, tz="UTC"))
    extra = [S[w].assign(timestamp=S[w].timestamp + pd.Timedelta(milliseconds=k + 1),
                         request_id=S[w].request_id + f"_dup{k + 1}") for k in range(multiplier - 1)]
    return pd.concat([S] + extra, ignore_index=True).sort_values("timestamp", kind="stable").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--openai", required=True); ap.add_argument("--gemini", required=True)
    ap.add_argument("--prices", required=True); ap.add_argument("--out", default="results")
    ap.add_argument("--runs", type=int, default=200, help="bootstrap months (run 0 is always real October)")
    ap.add_argument("--block-hours", type=int, default=12)
    ap.add_argument("--window-days", type=float, default=3, help="blocks are drawn from within +/- this many days")
    ap.add_argument("--quota-split", choices=["spend", "even"], default="spend")
    ap.add_argument("--estimate", choices=["online", "month"], default="online")
    ap.add_argument("--shock-tenant", default="org-engineering-dev")
    ap.add_argument("--shock-from", default="2026-10-12"); ap.add_argument("--shock-to", default="2026-10-15")
    ap.add_argument("--shock-multiplier", type=int, default=3); ap.add_argument("--shock-budget", type=int, default=85)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--strict", action="store_true", help="stop on invalid records instead of excluding them")
    ap.add_argument("--run-legacy-experiments", action="store_true",
                    help="EXPENSIVE: explicitly opt into the obsolete four-policy admission experiments; default prepares data only")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    checks = []

    # -- clean + price
    df = clean_telemetry(a.openai, a.gemini, a.strict)
    P = read_prices(a.prices)
    df.drop(columns=["error"]).to_csv(out / "clean_requests.csv", index=False)
    df[df.exclude_reason != ""][["request_id", "timestamp", "provider", "tenant", "model", "status", "exclude_reason"]] \
        .to_csv(out / "excluded_rows.csv", index=False)
    S = df[df.exclude_reason == ""].reset_index(drop=True)
    S["expected_output_tokens"] = expected_output(S, a.estimate)
    S.groupby(["tenant", "model"]).agg(requests=("request_id", "size"), median_output=("output_tokens", "median")) \
        .reset_index().to_csv(out / "expected_output.csv", index=False)
    teams = sorted(S.tenant.unique())
    A = Arrays(S, P, S.expected_output_tokens.values, teams)
    S["real_cost"] = A.real; S["expected_cost"] = A.exp
    S["token_bucket"] = pd.Categorical.from_codes(A.bucket, BUCKETS)
    S[["request_id", "timestamp", "provider", "tenant", "model", "input_tokens", "cached_tokens", "output_tokens",
       "expected_output_tokens", "token_bucket", "real_cost", "expected_cost"]].to_csv(out / "requests_sim.csv", index=False)
    write_analysis(df, S, out)
    if not a.run_legacy_experiments:
        print(f"Prepared {len(S):,} eligible requests and descriptive summaries; no simulation executed.")
        return
    BASE = A.real.sum()
    spend_by_team = pd.Series(A.real).groupby(A.tenant).sum().reindex(range(len(teams))).values
    shares = spend_by_team / BASE if a.quota_split == "spend" else np.full(len(teams), 1 / len(teams))
    print(f"rows {len(df):,} | used {len(S):,} | excluded {len(df) - len(S):,} | October cost ${BASE:,.2f}")

    # -- bootstrap workloads
    nslots = int(NDAYS * 24 / a.block_hours); bsec = a.block_hours * 3600
    secs = A.tfrac * NDAYS * 86400
    slot = np.minimum((secs // bsec).astype(int), nslots - 1)
    slot_rows = [np.flatnonzero(slot == s) for s in range(nslots)]
    win = int(round(a.window_days * 24 / a.block_hours))
    rng = np.random.default_rng(a.seed)

    def workload(r):
        if r == 0:
            return np.arange(len(S)), A.tfrac
        picks = [rng.integers(max(0, p - win), min(nslots, p + win + 1)) for p in range(nslots)]
        idx = np.concatenate([slot_rows[s] for s in picks])
        tf = np.concatenate([(p * bsec + secs[slot_rows[s]] - s * bsec) / (NDAYS * 86400) for p, s in enumerate(picks)])
        return idx, np.clip(tf, 0, 0.999999)

    rows, trace, bucket_rows = [], [], []
    for r in range(a.runs + 1):
        idx, tf = workload(r); w = A.take(idx, tf)
        ten, bk = A.tenant[idx], A.bucket[idx]; n_t = np.bincount(ten, minlength=len(teams))
        for bp in BUDGET_LEVELS:
            B = BASE * bp / 100
            for pol in POLICIES:
                adm, dn, charged, spent_day, frd = run(pol, B, shares, w)
                rate_t = np.bincount(ten[adm], minlength=len(teams)) / np.maximum(n_t, 1) * 100
                spent = charged.sum()
                if r == 0:  # invariants, checked on the real month
                    assert abs(spent - spent_day.sum()) < 1e-6
                    assert (~adm & dn).sum() == 0
                    if pol in ("fcfs", "routing"):
                        assert spent <= B * 1.01, (pol, bp, spent, B)
                    if pol == "fcfs" and bp == 100:
                        checks.append(f"fcfs at 100% admits {adm.mean() * 100:.2f}% (expected ~100%)")
                rows.append({"policy": pol, "budget_pct": bp, "run_id": r, "total_requests": len(idx),
                             "admitted_pct": adm.mean() * 100,
                             **{f"admitted_pct_{t}": rate_t[k] for k, t in enumerate(teams)},
                             "fairness_sd": rate_t.std(), "downgraded_pct": dn.mean() * 100,
                             "total_cost_pct": spent / BASE * 100, "unused_budget_pct": (B - spent) / BASE * 100,
                             "overspend_usd": max(0.0, spent - B),
                             "budget_exhausted_day": frd + 1 if frd >= 0 else np.nan,
                             "demand_cost_pct": w["real"].sum() / BASE * 100})
                if r == 0:
                    day = (tf * NDAYS).astype(int); cum = np.cumsum(spent_day)
                    served = np.bincount(day[adm], minlength=NDAYS) / np.maximum(np.bincount(day, minlength=NDAYS), 1) * 100
                    trace += [{"policy": pol, "budget_pct": bp, "day": d + 1,
                               "budget_left_pct": round(max(0.0, (B - cum[d]) / B * 100), 2),
                               "served_pct_day": round(served[d], 2)} for d in range(NDAYS)]
                if bp == 70:
                    key = ten * 3 + bk; tot = np.bincount(key, minlength=len(teams) * 3)
                    ok = np.bincount(key[adm], minlength=len(teams) * 3)
                    bucket_rows += [{"policy": pol, "run_id": r, "tenant": teams[j // 3], "bucket": BUCKETS[j % 3],
                                     "requests": int(tot[j]), "admitted_pct": ok[j] / tot[j] * 100}
                                    for j in range(len(tot)) if tot[j]]
        if r % 50 == 0:
            print(f"  month {r}/{a.runs}", flush=True)

    R = pd.DataFrame(rows); R.round(3).to_csv(out / "results.csv", index=False)
    pd.DataFrame(trace).to_csv(out / "trace.csv", index=False)
    pct = lambda p: (lambda s: np.nanpercentile(s, p) if s.notna().any() else np.nan)
    Bk = pd.DataFrame(bucket_rows)
    Bk.groupby(["policy", "tenant", "bucket"]).agg(requests_median=("requests", "median"),
        admitted_pct_median=("admitted_pct", "median"), admitted_pct_p5=("admitted_pct", pct(5)),
        admitted_pct_p95=("admitted_pct", pct(95))).round(2).reset_index().to_csv(out / "exp2_buckets.csv", index=False)
    boot = R[R.run_id > 0] if a.runs else R
    boot.groupby(["policy", "budget_pct"]).agg(admitted_pct_p5=("admitted_pct", pct(5)),
        admitted_pct_p50=("admitted_pct", "median"), admitted_pct_p95=("admitted_pct", pct(95)),
        cost_pct_p50=("total_cost_pct", "median"), fairness_sd_p50=("fairness_sd", "median"),
        exhausted_day_p50=("budget_exhausted_day", "median"), downgraded_pct_p50=("downgraded_pct", "median")) \
        .round(2).reset_index().to_csv(out / "exp3_summary.csv", index=False)

    # -- Exp 4: noisy neighbour
    ex = []
    for label, D in [("no shock", S), ("shock", inject_demand_shock(S, a.shock_tenant, a.shock_from, a.shock_to, a.shock_multiplier))]:
        est = expected_output(D, a.estimate); A2 = Arrays(D, P, est, teams); w = A2.take(np.arange(len(D)), A2.tfrac)
        inw = ((D.timestamp >= pd.Timestamp(a.shock_from, tz="UTC")) & (D.timestamp < pd.Timestamp(a.shock_to, tz="UTC"))).values
        after = (D.timestamp >= pd.Timestamp(a.shock_to, tz="UTC")).values; isT = (D.tenant == a.shock_tenant).values
        for pol in POLICIES:
            adm, dn, charged, spent_day, frd = run(pol, BASE * a.shock_budget / 100, shares, w)
            ex.append({"scenario": label, "policy": pol, "budget_pct": a.shock_budget,
                       "others_admitted_pct_during_shock": adm[inw & ~isT].mean() * 100,
                       "others_admitted_pct_after_shock": adm[after & ~isT].mean() * 100,
                       "spiking_tenant_admitted_pct_during_shock": adm[inw & isT].mean() * 100,
                       "all_admitted_pct": adm.mean() * 100,
                       "budget_exhausted_day": frd + 1 if frd >= 0 else np.nan})
    pd.DataFrame(ex).round(2).to_csv(out / "exp4_shock.csv", index=False)

    # -- reproducibility check: same seed, same answer
    w0 = A.take(np.arange(len(S)), A.tfrac)
    x1 = run("adaptive", BASE * .7, shares, w0)[0]; x2 = run("adaptive", BASE * .7, shares, w0)[0]
    assert (x1 == x2).all(); checks.append("same inputs give identical decisions")
    checks.append("realized spend equals sum of daily spend for every policy/budget (real October)")
    checks.append("no request is both refused and downgraded")
    checks.append("fcfs and routing never overspend more than 1% (estimate vs realized cost)")
    (out / "checks.txt").write_text("\n".join(checks) + "\n")

    json.dump({"rows_total": int(len(df)), "rows_used": int(len(S)),
               "excluded": df[df.exclude_reason != ""].exclude_reason.value_counts().to_dict(),
               "baseline_october_cost_usd": round(float(BASE), 2), "budgets_pct": list(BUDGET_LEVELS),
               "policies": list(POLICIES), "bootstrap_months": a.runs, "block_hours": a.block_hours,
               "window_days": a.window_days, "seed": a.seed, "quota_split": a.quota_split,
               "quota_shares": dict(zip(teams, np.round(shares, 4).tolist())), "estimate": a.estimate,
               "prices": P.reset_index().to_dict("records"),
               "shock": {"tenant": a.shock_tenant, "from": a.shock_from, "to": a.shock_to,
                         "multiplier": a.shock_multiplier, "budget_pct": a.shock_budget}},
              open(out / "settings.json", "w"), indent=2, default=str)
    print("done:", out.resolve())


if __name__ == "__main__":
    main()
