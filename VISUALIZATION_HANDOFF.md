# Visualization handoff

Use `results/canonical/` directly from the `simulation-integration` GitHub branch.
These are **pre-correction, provisional modeled results**. No expensive experiment
was rerun. `manifest.json` records source paths, hashes and export rules.

| Files | Purpose |
|---|---|
| `policies/run_metrics.csv` | Primary six-policy x four-budget comparison: 24 replay runs |
| `policies/tenant_metrics.csv` | Six operational tenants per run: 144 rows |
| `policies/policy_comparisons.csv` | Policy-minus-FCFS paired differences |
| `policies/budget_trajectories.csv` | Sampled budget curves with final state retained |
| `policies/experiment_summary.csv`, `regime_map.csv` | Historical summaries; prefer run-level records |
| `policies/scenario_metadata.json`, `findings.md` | Original configuration/report, retained as historical evidence |
| `local_bootstrap/`, `day_bootstrap/` | Each: replay plus ONE resampled workload at 70%; descriptive sensitivity only |
| `configuration/` | Micro-USD catalog, route map, citations and adaptation report |
| `results/analysis_*.csv` | Descriptive synthetic telemetry summaries, with whole-month scope |

Join tenants and trajectories to runs using `run_id` (many to one).
Tenant key: `(run_id, tenant)`; trajectory key: `(run_id, timestamp)`.
Pair policies within `scenario_id`, `budget_fraction`, `replicate`. Keep export
directories/methods separate: IDs may coincide across methods.
Fractions: .5, .7, .85, 1.0. Policies: FCFS, Quotas (equal), TrainingQuotas,
Adaptive, Pacing, Threshold. No routing is included in this comparison.

- Fully completed: `completed_original`; fraction: `completion_rate_original`.
- Denominators: `request_count` or tenant `demand_requests`.
- `admitted` includes truncations; never label it fully served.
- `rejected` and `truncated` are disjoint; divide by demand for rates.
- Divide `*_micro_usd` by 1,000,000 for USD; multiply rates by 100 for percent.
- `min_tenant_completion_rate`: minimum across billing/project groups.
- `max_min_completion_gap`: rate difference; multiply by 100 for percentage points.
- `paired_completed_original_difference`: absolute count difference from FCFS.

Do not chart historical `cost_weighted_served_share`, subgroup cost-per-completion,
`tenant_remaining`, hindsight gaps, or exhaustion fields without METHODOLOGY.md's
caveats. Singleton/two-observation interval columns do not establish uncertainty.
Automatic findings are historical reports, not reviewed hypothesis verdicts.

## Interpretation

The evaluation has 154,278 requests after 38,569 training requests; its reference
is $4,398.736885. The $5,710.576193 whole-month reference and online FCFS runs
describe a different experiment. Telemetry is synthetic. Policies and budgets
are simulated; routing configurations are counterfactual and quality is unmeasured.

The 1,024-token cap and mean reservation truncate even without budget scarcity:
100%-budget FCFS admits everyone, completes 48,585 and truncates 105,693.
At 70%, completions are FCFS 42,573; Quotas 36,641; TrainingQuotas 44,699;
Adaptive 45,768; Pacing 46,217; Threshold 47,384. These remain pre-correction.
Adaptive adds 3,195 over FCFS while engineering loses 1,900; show both.

Suggested figures: stacked outcomes by policy/budget; tenant completion changes;
quota unused funds versus denials; sampled budget curves. Exact first refusal
cannot be inferred from sampled curves. Do not extrapolate rankings or use causal
titles about learning or quality. Existing `figures/` and charts remain legacy work.
