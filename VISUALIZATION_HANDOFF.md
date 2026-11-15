# Visualization handoff

**Start with [results/presentation/](results/presentation/).** Download individual
CSVs from GitHub; no simulator run is needed. The [dictionary](results/presentation/data_dictionary.md)
defines every column and unit. [Provenance](results/presentation/provenance.json)
records saved source paths and hashes.

## Historical October: six tenants and six policies

These are **pre-correction, provisional** results from synthetic October telemetry,
with 154,278 evaluation requests. Preserve that label in captions.

| Chart | Exact file and columns | Message | Caveat |
|---|---|---|---|
| Stacked outcomes by policy | [policy_budget_summary.csv](results/presentation/policy_budget_summary.csv): filter `budget_pct=70`; `policy`, `completion_pct`, `truncation_pct`, `rejection_pct` | Denial and partial execution are different outcomes | Percentages sum to 100; admissions include truncations |
| Utilization and unused money | Same CSV: `policy`, `budget_utilization_pct`, `unused_budget_usd`; facet by `budget_pct` | Quotas can deny requests while money remains unused | USD is modeled, not billed; tiny balances are not exactly zero |
| Tenant winners and losers: diverging dots | [tenant_tradeoffs_70pct.csv](results/presentation/tenant_tradeoffs_70pct.csv): `tenant`, `policy`, `completion_difference_pp`, `completion_pct` | Aggregate gains can conceal a tenant loss | Tenants are operational groups, not demographics |
| Policy changes across budgets: lines or small multiples | [policy_budget_summary.csv](results/presentation/policy_budget_summary.csv): `budget_pct`, `completion_pct`, `policy` | Rankings depend on scarcity | Four distinct scenarios; connecting lines are guides, not tested intermediate budgets |
| Aggregate versus access floor: scatter | Same CSV: `completion_pct`, `min_tenant_completion_pct`, `policy`, `budget_pct` | Completion count and access protection differ | Minimum rate does not describe every tenant |
| Bootstrap method probe: paired dots | [bootstrap_methods_70pct.csv](results/presentation/bootstrap_methods_70pct.csv): `bootstrap_method`, `replicate`, `workload_kind`, `policy`, `completion_difference_pp` | Local versus whole-day sampling changes effect magnitude | One resample per method; no intervals or robustness claim |

Historical policy key: `(policy, budget_pct)`; tenant key: `(tenant, policy)`.
Bootstrap key: `(bootstrap_method, replicate, policy)`. Replicate 0 is the same
replay repeated under both method labels, not two independent observed months.
FCFS differences match the same workload and budget; use zero as the reference.

At 70%, fully completed requests are FCFS 42,573; Quotas 36,641; TrainingQuotas
44,699; Adaptive 45,768; Pacing 46,217; Threshold 47,384. Equal quotas leave
$741.27 while rejecting 33,745 requests. Adaptive adds 3,195 over FCFS while
engineering-dev loses 1,900: show the aggregate and tenant view together.

Mean reservations and the 1,024-token cap matter: at 100% reference budget,
FCFS completes 48,585 and truncates 105,693 despite admitting everyone. Those
losses cannot be attributed solely to scarcity. Repaired code does not
retrospectively validate the historical numbers.

## Fictional Monte Carlo pilot: separate from October

| Chart | Exact file and columns | Message | Caveat |
|---|---|---|---|
| Paired-effect strip/box plot | [monte_carlo_pilot_replicates.csv](results/presentation/monte_carlo_pilot_replicates.csv): filter `replicate>0`, `policy!=FCFS`; `policy`, `completion_difference_pp` | Adaptive changes sign; Pacing's count gain persists in this fixture | Only 29 conditional synthetic resamples |
| Median and spread: point with IQR | [monte_carlo_pilot_summary.csv](results/presentation/monte_carlo_pilot_summary.csv): `policy`, `median_completion_difference_pp`, `q25_completion_difference_pp`, `q75_completion_difference_pp` | Show magnitude and variability together | Outcome spread, not confidence intervals |
| Replay versus resamples: dots | Replicate CSV: `replicate`, `workload_kind`, `policy`, `completion_pct` | One replay can give a misleading ranking | Replay 0 is excluded from resample summaries |
| Ranking sensitivity: stacked counts | Summary CSV: `policy`, `wins`, `ties`, `losses`, `strict_ranking_reversals` | Adaptive reverses its replay ordering in 16/29 draws | These comparisons are against FCFS, not all-policy ranking probabilities |
| Counts versus access floor: scatter | Replicate CSV: `completion_pct`, `min_tenant_completion_pct`, `policy` | Higher count need not protect the worst tenant | Fictional workload, tenants and prices |

Pilot key: `(replicate, policy)`; three policies per workload. Randomness comes
from local-block resampling. Training estimates stay fixed; routing and estimator
noise are zero. The source has 2,000 requests: 400 training and 1,600 evaluation.
Pacing's median paired gain is +11.75 pp; Adaptive's is -0.125 pp. See the
[findings](documentation/MONTE_CARLO.md) and [mechanism investigation](documentation/PACING_INVESTIGATION.md)
for why count gains do not establish useful output or institutional superiority.

## Chart conventions

- `_pct` columns are already 0–100 percentages; do not multiply again.
- `_pp` columns are percentage-point differences, not relative percent changes.
- USD columns are already dollars; no further micro-unit conversion is needed.
- Use `completed_requests` for full completion; never label admissions fully served.
- Carry `dataset` and `result_status` into captions and provenance.
- Do not use causal titles about learning, model quality or institutional savings.

Original [canonical tables](results/canonical/) remain available for more columns;
read their historical metric caveats in the [methodology](documentation/METHODOLOGY.md).
Existing [figures](figures/static/) and [chart scripts](charts/) remain unchanged.
Their simulation panels use the legacy pipeline and cannot be relabeled as these
modular results. Routing is not part of this six-policy comparison.
