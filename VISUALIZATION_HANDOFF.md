# Visualization handoff

Use **[results/presentation/](results/presentation/)** for every final chart. All files are committed and small. No simulation or raw telemetry is needed. The [dictionary](results/presentation/data_dictionary.md) defines every column; [provenance](results/presentation/provenance.json) records source hashes. Rebuild saved-result aggregates with `python tools/build_presentation.py`.

## Seven-chart narrative

| Chart title / type | Exact dataset and columns | Main message | Caption caveat |
|---|---|---|---|
| 1. A small request class dominates modeled cost - paired horizontal bars | `results/presentation/descriptive_cost_by_model.csv`: `model`, `call_share_pct`, `cost_share_pct` | o1-preview is 5.33% of eligible calls and 50.73% of modeled cost | Descriptive full-month synthetic telemetry; floating-price reconstruction, not billing |
| 2. Model mix and caching change over October - two-panel weekly lines by tenant | `results/presentation/descriptive_weekly_trend.csv`: `tenant`, `week`, `calls_using_cache_pct`, `premium_model_pct` | Teams differ in their usage trends | Association; avoid claims that teams learned or caching caused measured savings |
| 3. Scarcity changes outcomes and idle money - stacked outcomes with utilization panel | `results/presentation/policy_budget_summary.csv`: `policy`, `budget_pct`, `completion_pct`, `truncation_pct`, `rejection_pct`, `unused_budget_usd`, `budget_utilization_pct` | Equal Quotas can reject requests while money remains unused | Historical pre-correction replay, 154,278 evaluation requests; cap 1,024 and mean reservations; facet 50/70/85/100% budgets |
| 4. More completions can hide a tenant loss - diverging dots with aggregate annotation | `results/presentation/tenant_tradeoffs_70pct.csv`: `tenant`, `policy`, `completion_difference_pp`, `completion_difference_requests`; aggregate counts from chart 3 at 70% | Historical Adaptive gains 3,195 overall but engineering-dev loses 1,900 | Same historical population as chart 3; tenants are operational groups |
| 5. Do policy gains survive matched workload changes? - paired-effect strip with median/IQR | `results/presentation/monte_carlo/replicate_results.csv`: filter `replicate>0`, `policy!=FCFS`; `policy`, `completion_difference_pp`; summary `paired_effects.csv`: `median_difference_pp`, `q25_difference_pp`, `q75_difference_pp`, `p05_difference_pp`, `p95_difference_pp` | Threshold > Pacing > Adaptive in all 49 resamples | Corrected synthetic October subset, ~5,000 requests, 70% budget, mean reservations, cap 8,192; conditional spread, not real-world CIs |
| 6. Aggregate gains and access floors differ - tenant heatmap plus outcome/output panel | `results/presentation/monte_carlo/tenant_outcomes.csv`: `tenant`, `policy`, `median_difference_pp`; `policy_summary.csv`: `median_completion_pct`, `median_truncation_pct`, `median_rejection_pct`, `median_min_tenant_completion_pct`, `median_delivered_output_tokens` | Adaptive loses engineering access; Pacing/Threshold improve every tenant but produce more partial outputs | Same study as chart 5; delivered tokens include partial answers, not quality; separate column medians need not sum to 100 |
| 7. Reservation assumptions change the answer - matched mean/Q90 slope chart | `results/presentation/monte_carlo/reservation_sensitivity.csv`: `policy`, `mean_reservation_median_completion_pct`, `quantile_reservation_median_completion_pct`, `mean_reservation_paired_median_pp`, `quantile_reservation_paired_median_pp` | Pacing's positive effect persists but grows from ~10.12 to ~22.27 pp | Ten matched stochastic resamples, three policies; mean uses those same ten draws, not all 49; no Threshold Q90 ranking claim |

Descriptive fingerprints and daily HTTP errors are in `descriptive_team_summary.csv` and `descriptive_rate_limits_daily.csv`. HTTP 429 errors are telemetry outcomes, different from simulated budget rejection. Historical method probes are in `bootstrap_methods_70pct.csv`: each method has the same replay plus **one** resample, insufficient for intervals or a robustness claim. Keep that comparison supplemental.

## Populations and joins

| Family | Population / interpretation | Keys |
|---|---|---|
| Descriptive | Full synthetic month; usage and reconstructed floating-price costs | model, tenant, tenant/week, or day/provider/tenant |
| Historical replay | 154,278 evaluation requests; pre-correction provisional; 24 runs | `(policy, budget_pct)`; tenant `(tenant, policy)` at 70% |
| Historical bootstrap probe | Replay plus one resample for each method | `(bootstrap_method, replicate, policy)` |
| Corrected Monte Carlo | Fixed 5,000-request subset; replay plus 49 variable-count resamples | `(replicate, policy)`; tenant summaries `(tenant, policy)` |
| Reservation sensitivity | Same first ten stochastic draws under mean and Q90 | `policy`; matched before aggregation |

Carry `dataset`, `result_status`, `budget_pct` and `reservation_mode` where present into captions. Replicate 0 is replay and never belongs in the resample distribution. Completion, truncation and rejection denominators include **all demand**. `_pct` is already 0-100; `_pp` is an absolute percentage-point difference. `_usd` is already dollars. Match FCFS within the same replicate and budget. Never join historical and subset runs by policy alone or present their difference as a single causal effect.

Use `ranking_stability.csv` for pairwise ranking counts, `sampling_audit.csv` for representativeness, and Q1-Q4 in `policy_summary.csv` for completion by original input-plus-output size. See [MONTE_CARLO.md](documentation/MONTE_CARLO.md).

## Existing interactive work

[Story](figures/story.html) and [dashboard](figures/dashboard.html) use descriptive summaries, historical chart-ready tables with canonical trajectories, and the corrected Monte Carlo presentation tables. Their builders are [make_story.py](charts/make_story.py) and [make_dashboard.py](charts/make_dashboard.py), with adjacent templates. Their established input paths remain unchanged, including tracked cleaned telemetry. The updated HTML includes separate corrected Monte Carlo panels. Treat historical recommendations as illustrative and keep the two populations labeled. Accessibility descriptions are consolidated in [docs/ALT_TEXT.txt](docs/ALT_TEXT.txt).

The five retained [static figures](figures/static/) are descriptive. Their builder now accepts `python charts/make_static.py results/clean_requests.csv OUTPUT_DIRECTORY`. Do not regenerate committed figures during normal verification.
