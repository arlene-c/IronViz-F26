# Methodology and result status

## Preserved experiments

`results/canonical/` contains **pre-correction** historical outputs. Original
six-policy CSV/Parquet files under `outputs/authoritative_policies/` are unchanged.
The manifest records byte-identical copies and the explicitly downsampled export.
Original experiments did not embed a generating commit.

Source: 202,650 synthetic October 2026 records; 192,847 eligible. The leading
38,569 requests train estimates/weights; 154,278 evaluation requests span October
7-30. Full reference cost: $5,710.576193; evaluation: $4,398.736885. Component
costs are ceiled to micro-USD. These are modeled list-price costs, not bills;
price effective dates and omitted fees remain limitations.

Historical configurations: equal quotas; training-spend quotas; adaptive protected
borrowing (rho .1, one-hour window, limit .5); linear pacing (slack .05); tuned
threshold. Adaptive/pacing are fixed, not equally optimized. Mean reservations
and a 1,024-token cap truncate without scarcity. Threshold tuning used realized
training costs, unlike evaluation reservations/settlements. Roster and horizon
were inferred retrospectively. Repaired code does not validate those old results.

At 70%, completed originals: FCFS 42,573; equal quotas 36,641; training quotas
44,699; Adaptive 45,768; Pacing 46,217; Threshold 47,384. Equal quotas leave
$741.272122; Adaptive leaves $78.572794. Adaptive gains overall over FCFS while
engineering loses 1,900. At 100%, FCFS completes 48,585 and truncates 105,693.

Each bootstrap export has replay plus ONE resample: do not use percentile columns
as confidence intervals. Local 12-hour blocks retain approximate calendar position;
whole-day resampling scrambles October's trend. No routing policy is in this comparison.

## Accounting and interpretation

Cached input is a subset of input. Strict mode reserves before execution, limits
output to reservation and selected-model cap, then immediately settles/releases.
Soft compatibility mode may exceed reservations and global budget. Admission is
not completion. Routed outcomes use assumed replacement lengths and unchanged
input tokens; they are not measured quality-equivalent service.

Historical cost-weighted served share was spend/reference spend. Original/routed
subgroup cost ratios used all spending. Historical tenant_remaining was global
budget minus tenant spend, not an entitlement. Historical exhaustion time was
first global-fit denial, not zero balance. Original-model hindsight bounds are
not upper bounds for cheaper routed service. Avoid those interpretations in figures.

## Current-code corrections

Finalization corrections and verification are recorded here when complete.
The machine contract is documentation/DATA_CONTRACT.md. The original specification
and archived audits are development provenance, not current implementation claims.
