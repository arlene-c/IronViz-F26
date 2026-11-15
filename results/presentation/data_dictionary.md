# Presentation data dictionary

Chart-ready saved results only. Historical tables are pre-correction and provisional; the fictional pilot is exploratory.
All `_pct` columns are already 0-100 percentages; `_pp` columns are percentage-point differences. USD columns are modeled costs.
No routing is present. Admitted requests can truncate. No percentile field is an inferential confidence interval.

Historical policy key: `(policy, budget_pct)`; tenant key: `(tenant, policy)`; bootstrap key: `(bootstrap_method, replicate, policy)`;
pilot key: `(replicate, policy)`. Join pilot summary to replicates on policy only after selecting the intended replicate population.
Each historical bootstrap method contains the SAME replay plus ONE resample; do not count the duplicate replays as independent evidence.
Pilot summary uses only the 29 resamples; pilot replicates also includes replay 0. FCFS differences are zero by construction.

## policy_budget_summary.csv

All six policies at four modeled budgets in the historical October evaluation replay.

24 rows. Saved source paths and SHA-256 hashes are in [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | historical_pre_correction_provisional or exploratory_synthetic. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `source_run_id` | identifier | Original saved run identifier; scope with dataset and bootstrap_method when present. |
| `request_count` | requests | Demand denominator: evaluation requests, or tenant evaluation requests in the tenant table. |
| `completed_requests` | requests | Fully completed original requests; excludes truncations and counterfactual routing. |
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

Each of six historical operational tenants under six policies at 70% budget.

36 rows. Saved source paths and SHA-256 hashes are in [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | historical_pre_correction_provisional or exploratory_synthetic. |
| `tenant` | identifier | Operational billing/project group, not an individual or demographic group. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `source_run_id` | identifier | Original saved run identifier; scope with dataset and bootstrap_method when present. |
| `request_count` | requests | Demand denominator: evaluation requests, or tenant evaluation requests in the tenant table. |
| `completed_requests` | requests | Fully completed original requests; excludes truncations and counterfactual routing. |
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

Two historical sampling-method probes, each with the same replay and one distinct resample at 70%.

24 rows. Saved source paths and SHA-256 hashes are in [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | historical_pre_correction_provisional or exploratory_synthetic. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `source_run_id` | identifier | Original saved run identifier; scope with dataset and bootstrap_method when present. |
| `request_count` | requests | Demand denominator: evaluation requests, or tenant evaluation requests in the tenant table. |
| `completed_requests` | requests | Fully completed original requests; excludes truncations and counterfactual routing. |
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

## monte_carlo_pilot_summary.csv

Three policy summaries computed from 29 fictional local-block resamples, excluding replay.

3 rows. Saved source paths and SHA-256 hashes are in [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | historical_pre_correction_provisional or exploratory_synthetic. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `bootstrap_method` | label | local_12h: 12-hour blocks within +/-3 days; day_block: whole-day resampling. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `resamples` | workloads | Number of positive-replicate paired observations; excludes replay. |
| `median_completion_difference_pp` | percentage points | Median paired completion-rate difference against FCFS across resamples. |
| `q25_completion_difference_pp` | percentage points | 25th percentile of paired resample differences. |
| `q75_completion_difference_pp` | percentage points | 75th percentile of paired resample differences. |
| `min_completion_difference_pp` | percentage points | Minimum observed paired resample difference. |
| `max_completion_difference_pp` | percentage points | Maximum observed paired resample difference. |
| `p025_completion_difference_pp` | percentage points | 2.5th percentile of paired resample outcomes; descriptive, not a confidence bound. |
| `p975_completion_difference_pp` | percentage points | 97.5th percentile of paired resample outcomes; descriptive, not a confidence bound. |
| `wins` | workloads | Resamples where policy completion rate exceeds FCFS. |
| `ties` | workloads | Resamples with equal policy and FCFS completion rates; all FCFS rows tie themselves. |
| `losses` | workloads | Resamples where policy completion rate is below FCFS. |
| `win_pct` | percent | 100 times wins/resamples; conditional frequency, not real-world success probability. |
| `replay_completion_pct` | percent | Policy completion percentage in the separate original replay. |
| `replay_completion_difference_pp` | percentage points | Policy-minus-FCFS completion difference in replay, excluded from resample statistics. |
| `median_completion_pct` | percent | Median policy completion percentage across resamples. |
| `median_min_tenant_completion_pct` | percent | Median of each resample's minimum tenant completion percentage. |
| `median_budget_utilization_pct` | percent | Median policy budget utilization across resamples. |
| `strict_ranking_reversals` | workloads | Resamples with a strict sign opposite the replay policy-minus-FCFS effect; ties are excluded, null if replay tied. |

## monte_carlo_pilot_replicates.csv

Every policy/replicate from the fictional pilot: three policies, replay plus 29 resamples.

90 rows. Saved source paths and SHA-256 hashes are in [provenance.json](provenance.json).

| Column | Unit | Definition |
|---|---|---|
| `dataset` | label | Historical October replay/probe or fictional synthetic pilot; never pool these populations. |
| `result_status` | label | historical_pre_correction_provisional or exploratory_synthetic. |
| `policy` | label | FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold. |
| `source_run_id` | identifier | Original saved run identifier; scope with dataset and bootstrap_method when present. |
| `bootstrap_method` | label | local_12h: 12-hour blocks within +/-3 days; day_block: whole-day resampling. |
| `budget_pct` | percent | Modeled budget as a percentage of original-model reference expenditure for that workload. |
| `replicate` | integer | 0 is original replay; positive values identify resampled workloads. |
| `workload_kind` | label | replay, local_12h_block_bootstrap or day_block_bootstrap; keep replay separate. |
| `request_count` | requests | Demand denominator: evaluation requests, or tenant evaluation requests in the tenant table. |
| `completed_requests` | requests | Fully completed original requests; excludes truncations and counterfactual routing. |
| `completion_pct` | percent | 100 times completed_requests/request_count. |
| `rejected_requests` | requests | Requests denied execution; disjoint from completed and truncated. |
| `rejection_pct` | percent | 100 times rejected_requests/request_count. |
| `truncated_requests` | requests | Admitted executions that did not finish their original observed output. |
| `truncation_pct` | percent | 100 times truncated_requests/request_count. |
| `fcfs_completion_pct` | percent | Completion percentage for the matching FCFS baseline. |
| `completion_difference_pp` | percentage points | Policy completion percentage minus matching FCFS percentage; not relative percent change. |
| `min_tenant_completion_pct` | percent | Lowest completion percentage among operational tenants; not demographic fairness. |
| `budget_utilization_pct` | percent | 100 times expenditure/global budget. |
