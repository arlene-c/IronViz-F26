# Presentation data dictionary

One entry point for chart-ready data. Every CSV carries dataset and result_status labels.
Historical October replay: 154,278 evaluation requests; pre-correction and provisional.
Corrected October subset: 5,000 evaluation requests; separate replay + 49 resamples; all rates use all demand.
Descriptive telemetry: full synthetic month, floating-price reconstruction; observed synthetic usage, not simulated outcomes.
Reservation sensitivity: ten matched resamples, mean versus Q90; three policies only.
Percentages are already 0-100. Percentage points are absolute rate differences. USD is modeled, not billed.
Delivered output includes truncated output and does not measure usefulness. Ranges are conditional spreads, not real-world confidence intervals.

Historical key: (policy, budget_pct); tenant key: (tenant, policy); bootstrap key: (bootstrap_method, replicate, policy).
Monte Carlo key: (replicate, policy). Replicate 0 is replay, excluded from summary distributions.
Historical bootstrap methods each contain the SAME replay plus ONE resample. Never pool those with the corrected study.

## policy_budget_summary.csv

24 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `source_run_id` | identifier | Original saved run identifier; scope with dataset and bootstrap_method when present. |
| `request_count` | requests | Demand denominator: evaluation requests, or tenant evaluation requests in the tenant table. |
| `completed_requests` | requests | Fully completed original requests; excludes partial output and rejected requests. |
| `completion_pct` | percent | 100 times completed_requests/request_count. |
| `truncated_requests` | requests | Admitted executions that did not finish their original observed output. |
| `truncation_pct` | percent | 100 times truncated_requests/request_count. |
| `rejected_requests` | requests | Requests denied execution; disjoint from completed and truncated. |
| `rejection_pct` | percent | 100 times rejected_requests/request_count. |
| `admitted_requests` | requests | Completed plus truncated executions; not fully served requests. |
| `budget_usd` | modeled USD | Global budget converted from integer micro-USD; not an actual bill. |
| `spend_usd` | modeled USD | Realized execution expenditure, including truncated executions. |
| `unused_budget_usd` | modeled USD | Global budget minus execution expenditure; not unused reservations. |
| `budget_utilization_pct` | percent | 100 times expenditure/global budget. |
| `fcfs_completed_requests` | requests | Completed requests for the matching FCFS workload, budget and replicate; tenant-specific in tenant table. |
| `fcfs_completion_pct` | percent | Completion percentage for the matching FCFS baseline. |
| `completion_difference_requests` | requests | Policy completed count minus matching FCFS completed count. |
| `completion_difference_pp` | percentage points | Policy completion percentage minus matching FCFS percentage; not relative percent change. |
| `spend_difference_usd` | modeled USD | Policy spend minus matching FCFS spend; negative means lower expenditure. |
| `utilization_difference_pp` | percentage points | Policy budget utilization minus matching FCFS utilization. |
| `min_tenant_completion_pct` | percent | Lowest completion percentage among operational tenants; not demographic fairness. |
| `tenant_completion_gap_pp` | percentage points | Highest tenant completion rate minus lowest tenant completion rate. |

## tenant_tradeoffs_70pct.csv

36 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `tenant` | identifier | Operational billing/project group, not an individual or demographic group. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `source_run_id` | identifier | Original saved run identifier; scope with dataset and bootstrap_method when present. |
| `request_count` | requests | Demand denominator: evaluation requests, or tenant evaluation requests in the tenant table. |
| `completed_requests` | requests | Fully completed original requests; excludes partial output and rejected requests. |
| `completion_pct` | percent | 100 times completed_requests/request_count. |
| `fcfs_completed_requests` | requests | Completed requests for the matching FCFS workload, budget and replicate; tenant-specific in tenant table. |
| `fcfs_completion_pct` | percent | Completion percentage for the matching FCFS baseline. |
| `completion_difference_requests` | requests | Policy completed count minus matching FCFS completed count. |
| `completion_difference_pp` | percentage points | Policy completion percentage minus matching FCFS percentage; not relative percent change. |
| `rejected_requests` | requests | Requests denied execution; disjoint from completed and truncated. |
| `truncated_requests` | requests | Admitted executions that did not finish their original observed output. |
| `spend_usd` | modeled USD | Realized execution expenditure, including truncated executions. |
| `spend_difference_usd` | modeled USD | Policy spend minus matching FCFS spend; negative means lower expenditure. |

## bootstrap_methods_70pct.csv

24 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `source_run_id` | identifier | Original saved run identifier; scope with dataset and bootstrap_method when present. |
| `request_count` | requests | Demand denominator: evaluation requests, or tenant evaluation requests in the tenant table. |
| `completed_requests` | requests | Fully completed original requests; excludes partial output and rejected requests. |
| `completion_pct` | percent | 100 times completed_requests/request_count. |
| `truncated_requests` | requests | Admitted executions that did not finish their original observed output. |
| `truncation_pct` | percent | 100 times truncated_requests/request_count. |
| `rejected_requests` | requests | Requests denied execution; disjoint from completed and truncated. |
| `rejection_pct` | percent | 100 times rejected_requests/request_count. |
| `admitted_requests` | requests | Completed plus truncated executions; not fully served requests. |
| `budget_usd` | modeled USD | Global budget converted from integer micro-USD; not an actual bill. |
| `spend_usd` | modeled USD | Realized execution expenditure, including truncated executions. |
| `unused_budget_usd` | modeled USD | Global budget minus execution expenditure; not unused reservations. |
| `budget_utilization_pct` | percent | 100 times expenditure/global budget. |
| `fcfs_completed_requests` | requests | Completed requests for the matching FCFS workload, budget and replicate; tenant-specific in tenant table. |
| `fcfs_completion_pct` | percent | Completion percentage for the matching FCFS baseline. |
| `completion_difference_requests` | requests | Policy completed count minus matching FCFS completed count. |
| `completion_difference_pp` | percentage points | Policy completion percentage minus matching FCFS percentage; not relative percent change. |
| `spend_difference_usd` | modeled USD | Policy spend minus matching FCFS spend; negative means lower expenditure. |
| `utilization_difference_pp` | percentage points | Policy budget utilization minus matching FCFS utilization. |
| `min_tenant_completion_pct` | percent | Lowest completion percentage among operational tenants; not demographic fairness. |
| `tenant_completion_gap_pp` | percentage points | Highest tenant completion rate minus lowest tenant completion rate. |
| `bootstrap_method` | label | local_12h: 12-hour blocks within +/-3 days; day_block: whole-day resampling. |
| `replicate` | integer | 0 is original replay; positive values identify resampled workloads. |
| `workload_kind` | label | replay, local_12h_block_bootstrap or day_block_bootstrap; keep replay separate. |

## descriptive_cost_by_model.csv

5 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `provider` | label | Synthetic telemetry provider label. |
| `model` | label | Recorded original model identifier. |
| `calls` | requests | Eligible successful requests for model/weekly tables; operational calls excluding invalid records for tenant/daily tables. |
| `cost_usd` | modeled USD | cost; no verified invoice or price-effective-date claim. |
| `call_share_pct` | percent (0-100) | Share of eligible model requests or operational tenant calls, according to table grain. |
| `cost_share_pct` | percent (0-100) | Share of reconstructed floating-price expenditure among eligible requests. |

## descriptive_team_summary.csv

6 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `tenant` | identifier | Operational billing/project group, not an individual or demographic group. |
| `provider` | label | Synthetic telemetry provider label. |
| `successful_calls` | requests | Eligible successful requests for this tenant. |
| `cost_usd` | modeled USD | cost; no verified invoice or price-effective-date claim. |
| `tokens` | input + output tokens | Total original input plus output tokens for eligible requests; no utility weighting. |
| `median_prompt_tokens` | input tokens | Median original prompt length among eligible requests. |
| `premium_model_pct` | percent (0-100) | Share of eligible calls on gpt-4o, o1-preview or gemini-1.5-pro. |
| `calls_using_cache_pct` | percent (0-100) | Eligible requests with any cached input divided by eligible requests. |
| `cached_share_of_input_pct` | percent (0-100) | Cached input tokens divided by total input tokens. |
| `cost_share_pct` | percent (0-100) | Share of reconstructed floating-price expenditure among eligible requests. |
| `token_share_pct` | percent (0-100) | Share of eligible original input plus output tokens. |
| `calls` | requests | Eligible successful requests for model/weekly tables; operational calls excluding invalid records for tenant/daily tables. |
| `bad_request_pct` | percent (0-100) | HTTP 400 calls divided by operational calls, excluding invalid telemetry records. |
| `rate_limited_pct` | percent (0-100) | HTTP 429 calls divided by operational calls, excluding invalid telemetry records. |
| `call_share_pct` | percent (0-100) | Share of eligible model requests or operational tenant calls, according to table grain. |
| `testing_team` | boolean | Source-defined testing group: engineering-dev and sandbox-testing; not a demographic category. |

## descriptive_weekly_trend.csv

24 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `tenant` | identifier | Operational billing/project group, not an individual or demographic group. |
| `week` | calendar interval | October 1-7, 8-14, 15-21 or 22-30; final interval has nine days. |
| `calls` | requests | Eligible successful requests for model/weekly tables; operational calls excluding invalid records for tenant/daily tables. |
| `calls_using_cache_pct` | percent (0-100) | Eligible requests with any cached input divided by eligible requests. |
| `premium_model_pct` | percent (0-100) | Share of eligible calls on gpt-4o, o1-preview or gemini-1.5-pro. |
| `median_prompt_tokens` | input tokens | Median original prompt length among eligible requests. |
| `cost_usd` | modeled USD | cost; no verified invoice or price-effective-date claim. |
| `cost_per_day_usd` | modeled USD | cost per day; no verified invoice or price-effective-date claim. |
| `testing_team` | boolean | Source-defined testing group: engineering-dev and sandbox-testing; not a demographic category. |

## descriptive_rate_limits_daily.csv

180 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `day` | day of October | Calendar day in October 2026 UTC. |
| `provider` | label | Synthetic telemetry provider label. |
| `tenant` | identifier | Operational billing/project group, not an individual or demographic group. |
| `rate_limited_429` | requests | Calls with HTTP 429; observational telemetry outcome, not simulated budget rejection. |
| `bad_request_400` | requests | Calls with HTTP 400; not simulated budget rejection. |
| `calls` | requests | Eligible successful requests for model/weekly tables; operational calls excluding invalid records for tenant/daily tables. |

## monte_carlo/policy_summary.csv

6 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `reservation_mode` | label | mean, or mean_vs_q90 for the matched ten-resample reservation comparison. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `resamples` | workloads | Positive replicate count only; separate replay is excluded. |
| `replay_completion_pct` | percent | Policy completion percentage in the separate original replay. |
| `median_completion_pct` | percent | Median policy completion percentage across resamples. |
| `mean_completion_pct` | percent (0-100) | mean completion; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `median_rejection_pct` | percent (0-100) | median rejection; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `median_truncation_pct` | percent (0-100) | median truncation; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `median_budget_utilization_pct` | percent | Median policy budget utilization across resamples. |
| `median_min_tenant_completion_pct` | percent | Median of each resample's minimum tenant completion percentage. |
| `median_delivered_output_tokens` | output tokens | Median delivered output including partial outputs; not task utility. |
| `median_delivered_output_per_demand` | output tokens/request | Median delivered output divided by all demand, including rejected requests. |
| `replay_min_tenant_completion_pct` | percent (0-100) | replay min tenant completion; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `cap_exceeded_total` | admissions | Sum of admitted executions exceeding the model cap across resamples; not all demand. |
| `median_completion_q1_pct` | percent (0-100) | median completion q1; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `median_completion_q2_pct` | percent (0-100) | median completion q2; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `median_completion_q3_pct` | percent (0-100) | median completion q3; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `median_completion_q4_pct` | percent (0-100) | median completion q4; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |

## monte_carlo/paired_effects.csv

6 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `reservation_mode` | label | mean, or mean_vs_q90 for the matched ten-resample reservation comparison. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `resamples` | workloads | Positive replicate count only; separate replay is excluded. |
| `replay_difference_pp` | percentage points | replay difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `mean_difference_pp` | percentage points | mean difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `median_difference_pp` | percentage points | median difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `q25_difference_pp` | percentage points | q25 difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `q75_difference_pp` | percentage points | q75 difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `p05_difference_pp` | percentage points | p05 difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `p95_difference_pp` | percentage points | p95 difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `min_difference_pp` | percentage points | min difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `max_difference_pp` | percentage points | max difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `wins` | workloads | Resamples where policy completion rate exceeds FCFS. |
| `ties` | workloads | Resamples with equal policy and FCFS completion rates; all FCFS rows tie themselves. |
| `losses` | workloads | Resamples where policy completion rate is below FCFS. |
| `win_pct` | percent | 100 times wins/resamples; conditional frequency, not real-world success probability. |
| `reversals_from_replay` | workloads | Strict sign reversals of policy-minus-FCFS effect relative to replay. |
| `median_minimum_tenant_difference_pp` | percentage points | median minimum tenant difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |

## monte_carlo/tenant_outcomes.csv

36 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `reservation_mode` | label | mean, or mean_vs_q90 for the matched ten-resample reservation comparison. |
| `tenant` | identifier | Operational billing/project group, not an individual or demographic group. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `resamples` | workloads | Positive replicate count only; separate replay is excluded. |
| `median_completion_pct` | percent | Median policy completion percentage across resamples. |
| `median_difference_pp` | percentage points | median difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `p05_difference_pp` | percentage points | p05 difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `p95_difference_pp` | percentage points | p95 difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `median_rejection_pct` | percent (0-100) | median rejection; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `median_truncation_pct` | percent (0-100) | median truncation; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `win_pct` | percent | 100 times wins/resamples; conditional frequency, not real-world success probability. |
| `replay_completion_pct` | percent | Policy completion percentage in the separate original replay. |
| `replay_difference_pp` | percentage points | replay difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |

## monte_carlo/replicate_results.csv

300 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `reservation_mode` | label | mean, or mean_vs_q90 for the matched ten-resample reservation comparison. |
| `source_run_id` | identifier | Original saved run identifier; scope with dataset and bootstrap_method when present. |
| `replicate` | integer | 0 is original replay; positive values identify resampled workloads. |
| `workload_kind` | label | replay, local_12h_block_bootstrap or day_block_bootstrap; keep replay separate. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `request_count` | requests | Demand denominator: evaluation requests, or tenant evaluation requests in the tenant table. |
| `completed_requests` | requests | Fully completed original requests; excludes partial output and rejected requests. |
| `rejected_requests` | requests | Requests denied execution; disjoint from completed and truncated. |
| `truncated_requests` | requests | Admitted executions that did not finish their original observed output. |
| `completion_difference_pp` | percentage points | Policy completion percentage minus matching FCFS percentage; not relative percent change. |
| `minimum_tenant_difference_pp` | percentage points | minimum tenant difference; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `delivered_output_tokens` | output tokens | Total delivered output including partial outputs from truncated executions. |
| `completion_pct` | percent | 100 times completed_requests/request_count. |
| `rejection_pct` | percent | 100 times rejected_requests/request_count. |
| `truncation_pct` | percent | 100 times truncated_requests/request_count. |
| `budget_utilization_pct` | percent | 100 times expenditure/global budget. |
| `min_tenant_completion_pct` | percent | Lowest completion percentage among operational tenants; not demographic fairness. |
| `spend_usd` | modeled USD | Realized execution expenditure, including truncated executions. |
| `budget_usd` | modeled USD | Global budget converted from integer micro-USD; not an actual bill. |

## monte_carlo/sampling_audit.csv

139 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `reservation_mode` | label | mean, or mean_vs_q90 for the matched ten-resample reservation comparison. |
| `population` | label | training or evaluation population in the sampling audit. |
| `metric` | label | Marginal share, token statistic or modeled reference cost audited against the original population. |
| `category` | label | Tenant/model/calendar category or statistic within the audited metric. |
| `source_value` | see unit | Statistic for the original source population. |
| `subset_value` | see unit | Same statistic for the fixed selected subset. |
| `difference` | see unit | Subset minus source statistic; share differences are percentage points. |
| `unit` | label | Units of source/subset/difference; percentages use pp for their differences. |

## monte_carlo/ranking_stability.csv

15 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `reservation_mode` | label | mean, or mean_vs_q90 for the matched ten-resample reservation comparison. |
| `policy_a` | label | First policy in the pairwise ranking comparison. |
| `policy_b` | label | Second policy in the pairwise ranking comparison. |
| `replay_a_minus_b_pp` | percentage points | replay a minus b; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `resamples` | workloads | Positive replicate count only; separate replay is excluded. |
| `a_wins` | workloads | Resamples in which policy_a has more full completions than policy_b. |
| `ties` | workloads | Resamples with equal policy and FCFS completion rates; all FCFS rows tie themselves. |
| `b_wins` | workloads | Resamples in which policy_b has more full completions than policy_a. |
| `strict_reversals` | workloads | Strict opposite ordering from replay; ties excluded. |

## monte_carlo/reservation_sensitivity.csv

3 rows. Source hashes: [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `reservation_mode` | label | mean, or mean_vs_q90 for the matched ten-resample reservation comparison. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `resamples` | workloads | Positive replicate count only; separate replay is excluded. |
| `mean_reservation_median_completion_pct` | percent (0-100) | mean reservation median completion; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `quantile_reservation_median_completion_pct` | percent (0-100) | quantile reservation median completion; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `mean_reservation_median_truncation_pct` | percent (0-100) | mean reservation median truncation; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `quantile_reservation_median_truncation_pct` | percent (0-100) | quantile reservation median truncation; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `mean_reservation_median_rejection_pct` | percent (0-100) | mean reservation median rejection; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `quantile_reservation_median_rejection_pct` | percent (0-100) | quantile reservation median rejection; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens. |
| `mean_reservation_paired_median_pp` | percentage points | mean reservation paired median; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `quantile_reservation_paired_median_pp` | percentage points | quantile reservation paired median; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `quantile_reservation_paired_p05_pp` | percentage points | quantile reservation paired p05; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `quantile_reservation_paired_p95_pp` | percentage points | quantile reservation paired p95; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds. |
| `paired_sign_changes` | workloads | Matched resamples whose policy-minus-FCFS effect changes strict sign between mean and Q90 reservations. |
