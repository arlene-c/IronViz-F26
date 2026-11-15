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

Schema 2 corrections are implemented and covered by targeted small regressions:
integer ceiling arithmetic; catalog units/duplicate/value/pair validation;
UTC normalization; cleaned/reference attribute reconciliation; configured horizon
and explicit/training-only roster; selected-target full cap reservation; separate
cap/reservation flags and denial causes; settled policy entitlement balances;
aggregate reservation release; original-only reference-cost-weighted completion;
execution-group spending ratios; distinct first denial/global-fit denial/zero-balance
exhaustion; null incomparable routed hindsight gaps; training threshold reservations,
settlements and completion objective; saved tau; separate replay/bootstrap summaries;
lower-spend win direction; suppressed intervals with fewer than 20 resamples;
and condition-specific paired diagnostic points without averaged interval endpoints.

These corrections can change rankings and metric meanings. Historical tables remain
pre-correction and provisional. **No full-data corrected run has been performed.**
Use `python -m pytest -q` for safe tests: scenario-sweep tests are marked and excluded
by default. They must not be enabled during submission stabilization. Tests use
synthetic records only; no full-data command is executed. Horizon flags are required
for timed policies; FCFS quickstart does not require a horizon.

Original files under outputs remain local, with ambiguous development artifacts
retained rather than deleted. Historical audits were archived byte-for-byte. Raw
CSV/cache tracking was removed; local files and shared Git history are unchanged.
Raw CSVs already exist in upstream history, which was not rewritten.
The machine contract is documentation/DATA_CONTRACT.md. The original specification
and archived audits are development provenance, not current implementation claims.

## Finalization verification

Safe suite: 46 passed, 3 scenario-sweep tests deselected. Editable 0.2.0 installation
and pip dependency check passed. CLI generation/validation and one FCFS smoke run
used 16 synthetic requests (3 training, 13 evaluation); no full-data experiment ran.
CI repeats the safe checks; a hosted CI outcome is not claimed here. Curated byte
hashes are protected by .gitattributes across platforms. Legacy source, pricing,
analysis tables and visual assets remain unchanged.

Follow-up local correctness and small Monte Carlo validation are documented in
[documentation/VALIDATION.md](documentation/VALIDATION.md). Those exploratory
synthetic results do not replace or validate the curated historical results.
