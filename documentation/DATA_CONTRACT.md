# DATA CONTRACT

This contract describes Phase 4 inputs and generated outputs. Monetary values are integer micro-USD unless a column explicitly says otherwise. Budgets, tenant eligibility, reservation multipliers, cost noise, and routed outcomes are modeled scenario assumptions. `SYNTHETIC TEST DATA` is never CMU telemetry, a real bill, or a real price catalog. Routed outcomes are counterfactual and make no quality-equivalence claim.

## Inputs

Request CSV/Parquet columns:

| Column | Type | Meaning |
|---|---|---|
| `request_id` | string | Unique input request identifier |
| `timestamp` | ISO timestamp | Event time; rows must be chronological |
| `provider` | string | Provider label supplied by the data owner |
| `model` | string | Original model identifier |
| `tenant` | string | Billing/project group only |
| `input_tokens` | non-negative integer | Original input token count |
| `output_tokens` | non-negative integer | Observed original output token count |
| `cached_input_tokens` | integer in `[0,input_tokens]` | Cached subset of input tokens |
| `original_status` | string | Original request status; only `success` rows enter eligible demand |
| `reference_cost` | optional non-negative integer | Optional externally supplied reference cost in micro-USD; never inferred by the adapter |

The `validate-data` command writes `row_errors.csv` with one `row_error` string column. Invalid rows are reported and not silently normalized. The validation command exits nonzero when row errors exist.

Price-catalog JSON has top-level `version`, `price_unit`, and `rows`; each row has `provider`, `model`, `input_price`, `cached_input_price`, and `output_price`. Prices are integer micro-USD per one million tokens. Synthetic catalogs are explicitly labeled and are for tests only.

## Output Files

### `event_traces.parquet`

One row per request for trace-enabled runs (replay and configured bootstrap replicates). A unique `run_id` scopes the policy, scenario, budget, and replicate. This table is sufficient to reconstruct each decision, selected model, modeled budget change, and original-versus-routed outcome.

Columns, in order:

```text
run_id: string
scenario_id: string
seed: integer
timestamp: ISO timestamp
request_id: string
source_request_id: string
tenant: string
original_model: string
selected_model: string
policy: string
decision: ADMITTED | REJECTED
outcome: REJECTED | COMPLETED_ORIGINAL | TRUNCATED_ORIGINAL | COMPLETED_ROUTED_CF | TRUNCATED_ROUTED_CF
estimated_cost: integer micro-USD
reservation_before: integer micro-USD
reservation_after_settlement: integer micro-USD
realized_cost: integer micro-USD
global_remaining: integer micro-USD after event settlement
tenant_remaining: integer micro-USD after event settlement
cumulative_counts: integer
is_counterfactual: boolean
observed_original_output_tokens: integer
modeled_routed_output_tokens: nullable integer
allowed_output_tokens: integer actually served/billed
overrun: integer micro-USD
cost_uncertainty_multiplier: float
budget_fraction: float
budget_micro_usd: integer
workload_kind: replay | volume_reweighted_replay | day_block_bootstrap
replicate: integer
```

### `budget_timeseries.parquet`

Downsampled after-event states for all runs. The final event is always retained. Columns:

```text
run_id, scenario_id, seed, policy, budget_fraction, budget_micro_usd, replicate,
workload_kind, demand_imbalance, estimator_noise_sigma, routing_eligibility,
reservation_multiplier, routed_output_length_multiplier, timestamp, request_id,
global_remaining_micro_usd, cumulative_spend_micro_usd,
reservation_before_micro_usd, realized_cost_micro_usd, decision, outcome,
cumulative_counts
```

### `run_metrics.csv`

One row per policy/scenario/budget/replicate. Metadata columns:

```text
run_id, scenario_id, seed, policy, budget_fraction, budget_micro_usd, replicate,
workload_kind, demand_imbalance, estimator_noise_sigma, routing_eligibility,
reservation_multiplier, reservation_mode, reservation_quantile, output_cap,
model_output_caps, routed_output_length_multiplier, hindsight_max_count,
hindsight_max_min_rate, runtime_seconds
```

Metric columns:

```text
request_count, admitted, completed_original, completed_routed, completed_total,
rejected, truncated, admission_rate, completion_rate_original,
completion_rate_routed, completion_rate_total, realized_cost_micro_usd,
reserved_micro_usd, unused_reservation_micro_usd, overrun_micro_usd,
cost_per_completed_request_micro_usd, cost_per_original_completion_micro_usd,
cost_per_routed_completion_micro_usd, budget_utilization,
budget_remaining_micro_usd, budget_remaining_fraction,
time_to_budget_exhaustion_seconds, min_tenant_completion_rate,
max_min_completion_gap, jain_completion_rate, gini_completion_rate,
token_weighted_served_share, cost_weighted_served_share,
reference_cost_micro_usd, completion_size_q1, completion_size_q2,
completion_size_q3, completion_size_q4, gap_to_max_count_hindsight,
gap_to_max_min_rate_hindsight
```

`completed_total` is a count for comparison only; original and routed counts/rates remain separate. Routed completion count is not quality or utility.

### `tenant_metrics.csv`

One row per tenant and run, using the run metadata columns above, followed by:

```text
tenant, demand_requests, admitted, completed_original, completed_routed,
completed_total, rejected, truncated, admission_rate, completion_rate_original,
completion_rate_routed, completion_rate_total, realized_cost_micro_usd,
reference_cost_micro_usd, spend_share, demand_share,
token_weighted_served_share, cost_weighted_served_share
```

`tenant` is a billing/project group, not an individual identity.

### `experiment_summary.csv`

Grouped by:

```text
policy, budget_fraction, demand_imbalance, estimator_noise_sigma,
routing_eligibility, reservation_multiplier, reservation_mode, reservation_quantile,
output_cap, model_output_caps, routed_output_length_multiplier, replicates
```

For each metric `M` in

```text
admitted, completed_original, completed_routed, completed_total, rejected, truncated,
admission_rate, completion_rate_original, completion_rate_routed, completion_rate_total,
realized_cost_micro_usd, reserved_micro_usd, unused_reservation_micro_usd, overrun_micro_usd,
cost_per_completed_request_micro_usd, cost_per_original_completion_micro_usd,
cost_per_routed_completion_micro_usd, budget_utilization, budget_remaining_micro_usd,
budget_remaining_fraction, runtime_seconds, min_tenant_completion_rate, max_min_completion_gap,
jain_completion_rate, gini_completion_rate, token_weighted_served_share, cost_weighted_served_share,
completion_size_q1, completion_size_q2, completion_size_q3, completion_size_q4
gap_to_max_count_hindsight, gap_to_max_min_rate_hindsight
```

the exact columns are `mean_M`, `ci95_low_M`, and `ci95_high_M`.

For each paired metric `P` in

```text
paired_completed_total_difference, paired_realized_cost_micro_usd_difference,
paired_min_tenant_completion_rate_difference, paired_budget_utilization_difference
```

the exact columns are `mean_P`, `ci95_low_P`, `ci95_high_P`, `win_rate_P`, and `effect_size_P`. Differences are policy minus FCFS within the same sampled scenario. CIs are percentile intervals across replicates and describe workload resampling/model assumptions only.

### `policy_comparisons.csv`

One paired row per non-FCFS policy/scenario/budget/replicate. Key columns:

```text
scenario_id, budget_fraction, budget_micro_usd, replicate, demand_imbalance,
estimator_noise_sigma, routing_eligibility, reservation_multiplier,
routed_output_length_multiplier, policy
```

For each `M` in `completed_total`, `completed_original`, `completed_routed`, `realized_cost_micro_usd`, `cost_per_completed_request_micro_usd`, `min_tenant_completion_rate`, and `budget_utilization`, columns are `M`, `fcfs_M`, and `paired_M_difference`.

### `regime_map.csv`

Mean policy advantage over FCFS by policy, budget fraction, demand-imbalance regime, and estimator-uncertainty regime:

```text
policy, budget_fraction, imbalance_regime, uncertainty_regime,
completion_advantage_over_fcfs, min_tenant_rate_advantage_over_fcfs,
budget_utilization_advantage_over_fcfs
```

### `scenario_metadata.json`

Top-level keys:

```text
data_label, seed, catalog_version, training_request_count,
evaluation_request_count, excluded_request_count, training_window,
evaluation_window, bootstrap_method, paired_design, random_streams,
assumptions, config, experiment_runtime_seconds, scenarios
```

Each `scenarios` entry has `scenario_id`, `replicate`, `workload_kind`, `seed`, `request_count`, `reference_cost_micro_usd`, `demand_imbalance_factor`, `observed_tenant_volume_ratio`, `estimator_noise_sigma`, `reservation_multiplier`, `routing_eligibility_probability`, `routed_output_length_multiplier`, and `trace`.

### `findings.md`

Generated hypothesis verdicts (supported, not supported, or inconclusive), with fixture/modeling caveats. Missing sensitivity dimensions produce an explicit inconclusive verdict rather than an extrapolation.

## Diagnostic Images

The output directory contains these PNGs:

- `completion_vs_budget_fraction.png`: mean completed counts by policy and modeled budget fraction.
- `per_tenant_completion.png`: mean completion rates by billing/project group and policy.
- `budget_remaining_over_time.png`: downsampled modeled remaining budget for the first scenario.
- `paired_differences_ci.png`: paired completed-request differences versus FCFS with percentile intervals.
- `routing_sensitivity.png`: completion counts across modeled routing eligibility values for routed policies.

These are diagnostic views. The CSV and Parquet tables are the machine-readable source of truth.
