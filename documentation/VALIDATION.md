# Focused validation and Monte Carlo pilot

Local branch: `simulation-validation`, based on published `simulation-integration`
commit `1a424f5`. Follow-up publication is authorized only to the validation
branch; main and simulation-integration are preserved. No historical experiment
was rerun. Historical published results remain pre-correction.

## Confirmed fixes

- `experiments.py`: training output distributions now use `(provider, model)`;
  reservations use `(request_id, provider, model)`. Previously same-named models
  across providers could mix training outputs or overwrite a routed reservation.
- `engine.py`: accepts qualified reservation keys; legacy `(request_id, model)`
  keys remain compatible only when the model identifies a unique catalog provider.
  Ambiguous legacy keys fail explicitly rather than silently using the wrong price.
- `CostThreshold.fit`: includes the zero threshold among candidates. The previous
  candidate set could spend money without any completions when rejecting all
  positive-cost requests would win the declared completion/spend tie-break.
- Pytest discovery is restricted to `tests/`, preventing ignored source archives
  under outputs from being collected as duplicate test modules.

Other reviewed behavior did not need rewriting. Strict calibration settlements
and completion flags match small engine replays in mean, quantile and cap modes.
Cost-per-completion includes wasted truncated execution spend in its numerator;
subgroup ratios allocate spending by original/routed execution group. Zero
completion denominators are null. These are spending ratios, not marginal costs
or utility. Timed policies preserve prefixes with a fixed roster, horizon, budget
and estimator. Retrospective reference-budget normalization is a separate scenario
assumption and can change decisions when evaluation outputs change.

## Verification

`tests/test_monte_carlo.py`: 17 small checks, with at most 36 source requests and
three replicates per runner call. They cover seed reproducibility and distinct
draws (ignoring replicate-specific ID suffixes), whole-day/block record retention,
local calendar windows, identical workload/cost draws across policies and policy
order, training-only estimates, provider collisions, strict calibration replay,
prefix invariance, correct FCFS pairing, replay/resample separation, insufficient
resample interval suppression, and spending denominators.

Safe suite: **63 passed, 3 scenario-sweep tests deselected**. Figure generation is
disabled in the table-writer smoke test; no existing figures were regenerated.
Protected files are checked against a pre-validation SHA-256 snapshot: curated
exports/manifest, original 24-row run_metrics, figures and local raw CSVs.

## EXPLORATORY SYNTHETIC pilot

Reproduce only this bounded pilot with `python tools/run_monte_carlo_pilot.py`.
The script refuses to overwrite an existing destination. It never reads raw
telemetry or imports the legacy pipeline. No request-level trace file or figure
is written. Outputs remain ignored under `outputs/monte_carlo_pilot/`.

- 2,000 synthetic fixture requests; first 400 train; 1,600 evaluate.
- 30 total replicates: separate replay plus 29 local 12-hour resamples, +/-3 days.
- One scenario: 70% reference budget; FCFS, Adaptive, Pacing; no routing or estimator noise.
- Fixed seed 20261114; explicit tenants a/b/c (named tenant-a/b/c in the fixture).
- Evaluation horizon January 5-21, 2026 UTC. The final evaluation event is January
  20 at 23:45:36 UTC. Timestamps are uniformly spaced: 100 requests/day, 50/block.
- Fictional fixture prices are multiplied by 1,000 to reduce micro-USD rounding
  dominance; they are not historical or actual provider prices.
- Mean reservations; 1,024-token output cap; fixed default adaptive/pacing settings.
- 90 policy runs; measured runner wall time **14.444975 seconds**.
- All runs have 1,600 requests; outcomes and budgets reconcile; zero overrun,
  routing and retained event traces. No request in this pilot exceeds the cap;
  truncation comes from reservation shortfall.

### Replay versus resamples

| Policy | Replay completion | Resample median [Q25, Q75] | Replay minimum-tenant completion | Resample median minimum | Median utilization |
|---|---:|---:|---:|---:|---:|
| FCFS | 47.500% | 47.563% [46.438%, 48.063%] | 47.185% | 45.867% | 99.997% |
| Adaptive | 48.125% | 47.438% [46.438%, 48.063%] | 43.566% | 44.370% | 99.991% |
| Pacing | 59.375% | 59.313% [59.000%, 59.813%] | 59.115% | 57.882% | 99.997% |

| Paired completion difference vs FCFS | Replay | Resample median [Q25, Q75], pp | Min-max, pp | Wins/ties/losses |
|---|---:|---:|---:|---:|
| Adaptive | +0.625 pp | -0.125 [-0.438, +0.313] | -0.938 to +0.938 | 11 / 2 / 16 |
| Pacing | +11.875 pp | +11.750 [+11.250, +13.188] | +10.063 to +14.125 | 29 / 0 / 0 |

Adaptive's replay ordering against FCFS reverses strictly in 16/29 resamples
(55.2%), with two ties. Pacing never reverses against either policy. Descriptive
2.5th-97.5th percentile effect ranges are Adaptive [-0.850,+0.806] pp and Pacing
[+10.106,+13.688] pp. These are synthetic resampled outcome ranges, not confidence
intervals for real-world effects or evidence of institutional significance.

Pacing admits more requests: median rejections 170 versus FCFS 453, but also
produces more truncations (478 versus 390). Its count advantage therefore does
not establish improved answer utility. No imposed changing-cost trend exists in
this fixture; the pilot cannot attribute pacing gains to October's real chronology.
An allowance-based admission rule also selects among differently priced requests.

## Files and limits

- `policy_completion_rates.csv`: every policy/replicate rate, paired pp effect,
  minimum tenant rate, utilization and outcome counts (90 rows).
- `paired_effect_summary.csv`: resample medians, quartiles, ranges and win counts.
- `ranking_reversals.csv`: pairwise order changes relative to replay.
- `run_metrics.csv`, `tenant_metrics.csv`, `policy_comparisons.csv`,
  `experiment_summary.csv`, `scenario_metadata.json`: standard records/configuration.
- `verification.json`: protected-file and source hashes plus checks after the run.

Only 29 draws from 32 evaluation blocks, one fixed workload generator, one seed,
one budget and fixed training estimates are represented. Budgets are recomputed
as 70% of each sampled workload's reference expenditure; no fixed-dollar study,
training-window uncertainty, quality model or model-price uncertainty is tested.
Mean reservations still truncate requests even with ample money. A focused
full-data paired study is worthwhile only after choosing an execution definition
and generous-budget control; this pilot validates machinery, not a preferred
institutional policy. No such full-data study was run here.
