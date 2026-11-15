# Modeled October subset Monte Carlo study

**SYNTHETIC COMPETITION TELEMETRY / MODELED OUTCOMES.** These are conditional
workload-resampling results, not observed institutional performance or real-world
confidence intervals. No original historical result is replaced.

## Design and sampling

The corrected simulator at source revision
`828bb02e39d34592025394449d275e7ec33a0772` ran all six policies at 70% of each
replicate's modeled reference cost. The main experiment contains one replay and
49 stochastic resamples, totaling 300 policy runs. Summaries exclude replay.
Seed: **20261115**. Strict reservations and settlements are enabled; routing and
estimator noise are zero. Mean output reservations are trained once and fixed.
Model output caps are 8,192 tokens for each of the five models: a generous modeled
ceiling, not a claim about historical provider limits. No event traces are retained.

The fixed evaluation horizon is October 7, 2026 00:00 UTC through October 31
00:00 UTC (exclusive). The roster is org-engineering-dev, org-marketing-ai,
org-prod-core, prj-ai-enterprise-prod, prj-ai-r-and-d and
prj-ai-sandbox-testing. Each policy receives identical demand, cost multipliers,
budget and horizon within a replicate.

The source contains 192,847 eligible requests. Its first 38,569 form the original
training period; the remaining 154,278 form evaluation. Deterministic proportional
sampling selects **1,250 training and 5,000 evaluation** requests independently,
using largest-remainder allocation over 12-hour block x tenant x provider/model x
cache-used strata, then seeded sampling without replacement within each stratum.
Training and evaluation IDs are disjoint. The selected training ends October 6;
evaluation begins October 7. Model output estimates, tenant quota weights and
threshold calibration use training only. The configuration's training fraction
0.20004 is an adapter that splits the concatenated sample at exactly 1,250 rows.

Relative to the original evaluation period, maximum marginal share deviations
are 0.262 percentage points for tenants, 0.352 for models, 0.163 for providers,
0.108 for dates and 0.483 for hours. Cache use is 33.54% versus 33.73%; premium
model share is 0.655 pp higher. Mean input/output lengths are 7,305/1,197 tokens
versus 7,249/1,191. Modeled mean reference cost is $0.02954 versus $0.02851,
about 3.6% higher. This is representative sampling with finite-sample deviations,
not an exact reproduction of token tails or expenditure.

Each resample selects whole source 12-hour blocks within +/-3 days of each target
block, retaining within-block records and relative timestamps while retiming them
to the target. Demand varies from 4,975 to 5,022 requests. Budgets consequently
vary with each replicate's reference cost; they are identical across its policies.
Training data, estimates, prices, roster, horizon, policy settings, caps and seed
scheme stay fixed. Boundary blocks have fewer eligible neighbors. This local
resampling preserves approximate calendar position, not every temporal dependency.

## Main results

All rates below use **all requests**, including rejected and truncated requests,
as denominator. Full completion requires all original output. Values are medians
over the 49 resamples except the explicitly labeled mean completion column.
Separate column medians need not sum to 100%.

| Policy | Median full % | Mean full % | Rejected % | Truncated % | Budget used % | Minimum tenant full % |
|---|---:|---:|---:|---:|---:|---:|
| FCFS | 35.35 | 35.41 | 27.29 | 37.31 | 100.00 | 32.72 |
| Equal Quotas | 35.49 | 35.57 | 27.67 | 36.66 | 78.28 | 18.96 |
| Training Quotas | 39.36 | 39.37 | 19.55 | 41.23 | 97.98 | 31.88 |
| Adaptive | 40.22 | 40.25 | 17.91 | 41.98 | 100.00 | 28.38 |
| Pacing | 45.46 | 45.50 | 6.75 | 47.81 | 100.00 | 41.56 |
| Threshold | 47.63 | 47.66 | 2.44 | 50.03 | 96.79 | 43.13 |

Paired completion-rate differences versus **the same replicate's FCFS**, in
percentage points. Ranges are conditional empirical spreads, not formal CIs.

| Policy | Median gain | Q25-Q75 | P05-P95 | Wins / 49 |
|---|---:|---:|---:|---:|
| Equal Quotas | +0.26 | -0.14 to +0.46 | -0.61 to +0.83 | 31 |
| Training Quotas | +3.93 | +3.61 to +4.21 | +3.33 to +4.95 | 49 |
| Adaptive | +4.87 | +4.52 to +5.16 | +3.99 to +5.51 | 49 |
| Pacing | +10.16 | +9.80 to +10.37 | +9.48 to +10.71 | 49 |
| Threshold | +12.30 | +12.05 to +12.42 | +11.71 to +12.73 | 49 |

Threshold > Pacing > Adaptive holds in all 49 resamples. Adaptive falls below
Training Quotas in 3/49; Equal Quotas falls below FCFS in 18/49. These are the
only pairwise reversals relative to this subset's replay. The replay completion
rates are FCFS 35.24%, Equal Quotas 35.52%, Training Quotas 39.38%, Adaptive
40.76%, Pacing 45.76%, Threshold 47.72%; replay paired gains sit within the
observed resampled ranges.

### Demand size and output delivery

Quartiles use each replicate's original **input plus output tokens**, not cost or
output length alone. Entries are median full-completion percentages.

| Policy | Q1 smallest | Q2 | Q3 | Q4 largest | Median delivered output tokens |
|---|---:|---:|---:|---:|---:|
| FCFS | 36.78 | 31.76 | 37.46 | 35.70 | 3,904,378 |
| Equal Quotas | 41.47 | 27.96 | 31.95 | 40.78 | 3,819,083 |
| Training Quotas | 47.44 | 34.93 | 38.35 | 36.99 | 4,164,936 |
| Adaptive | 47.65 | 36.83 | 38.22 | 38.63 | 4,287,901 |
| Pacing | 51.32 | 43.58 | 43.84 | 43.26 | 4,772,947 |
| Threshold | 53.51 | 45.61 | 46.75 | 44.62 | 4,973,882 |

Delivered output includes partial outputs from truncated requests. Token totals
do not measure answer usefulness, model quality, tenant value or task success.
Pacing and Threshold increase both full completions and total delivered output,
while also producing more truncations. Equal Quotas' slight count advantage
coexists with less delivered output and substantial unused budget.

### Tenant tradeoffs

Pacing and Threshold improve every tenant versus FCFS in every resample.
Their tenant-specific median gains span +7.91 to +12.52 pp and +9.23 to
+15.36 pp respectively. Adaptive raises aggregate completions but reduces
engineering-dev by 6.43 pp (all 49 resamples); its median paired minimum-tenant
effect is -4.76 pp. Training Quotas reduces engineering-dev by 2.34 pp and
sandbox-testing by 1.50 pp. Equal Quotas favors the three prj tenants but harms
engineering-dev (-15.64 pp), marketing-ai (-9.93 pp), and prod-core (-10.14 pp).
Equal monetary shares do not imply equal completion rates when workloads differ.

## Caps and reservation sensitivity

50.56% of sampled original outputs exceed 1,024 tokens, but **none exceed
8,192**. Every main run has zero cap-exceeding admissions. All main truncations
are flagged as reservation shortfalls. Increasing the cap therefore removes
artificial cap censoring but does not cure mean-reservation truncation.

A 64-request FCFS sanity check with ample budget yields:

| Reservation / cap | Full | Truncated | Rejected | Cap-exceeding admissions |
|---|---:|---:|---:|---:|
| Mean / 1,024 | 12 | 52 | 0 | 52 |
| Mean / 8,192 | 34 | 30 | 0 | 0 |
| Training Q90 / 8,192 | 60 | 4 | 0 | 0 |

Flags can overlap: all 52 restrictive-cap truncations also have reservation
shortfalls, so these counts are not additive causal categories.

The narrow sensitivity check uses the same requests, seeds, per-replicate budgets
and 8,192 caps, comparing **ten matched stochastic resamples** (plus separate
replay). Only FCFS, Adaptive and Pacing are run. Median full completion rises
from 35.37% to 61.23% for FCFS, 40.17% to 70.45% for Adaptive, and 45.39% to
83.45% for Pacing. Median truncation drops respectively from 37.14/42.27/47.80%
to 6.87/7.90/9.67%. Paired median advantages become Adaptive +9.14 pp
(P05-P95 +8.28 to +10.62) and Pacing +22.27 pp (+21.83 to +23.53), versus
matched mean-reservation advantages +4.83 and +10.12 pp. Neither advantage
changes sign. **Direction is stable for these policies; magnitude is highly
reservation-dependent.** No conclusion about Threshold's Q90 ranking is possible.

Pacing admits in chronological order against released cumulative spending credit;
it has no queue or look-ahead. Smaller reservations can fit when larger ones fail.
Its advantage is mechanically consistent with time-dependent cost selection and
retaining budget for later arrivals. The present paired comparison does not isolate
how much of that advantage comes from calendar trends versus price/model mix.
No new admission-rule defect was identified; prior controlled validation is in
[the archived mechanism investigation](archive/PACING_INVESTIGATION.md).

## Historical comparison and limits

At 70%, the preserved historical replay ranks Threshold > Pacing > Adaptive >
Training Quotas > FCFS > Equal Quotas. This subset swaps the last two in replay,
and resampling shows that difference is unstable. Historical FCFS/Pacing/Threshold
full completion rates are approximately 27.60/29.96/30.71%, versus this subset's
35.24/45.76/47.72%. **These are not estimates of a single intervention:** sample
composition, training sample, corrected semantics, explicit horizon and output cap
differ. The full 154,278-request evaluation was not rerun. This study cannot
retroactively validate the historical completion counts or isolate each correction.

Other limits: synthetic telemetry; fixed, assumed prices; one budget and one block
scheme; only 49 primary resamples; no repeated sample selection or training
uncertainty; and no modeled response quality. Rare-model estimates are especially
sensitive: only 63 o1-preview training requests yield a mean of 2,293 tokens,
versus 2,485 in sampled evaluation. A future bounded study could assess training
sample sensitivity before making broader claims. This analysis supports a final
presentation of modeled tradeoffs and conditional uncertainty, not an institutional
recommendation or a universal policy winner.

## Runtime, verification and files

| Stage | Evaluation size | Total replicates | Policy runs | Runner seconds | Process wall seconds | Peak worker MiB |
|---|---:|---:|---:|---:|---:|---:|
| Tiny pilot | 500 | 3 | 9 | 0.51 | 2.22 | 129.12 |
| Configuration pilot | 5,000 | 3 | 18 | 6.64 | 8.24 | 150.21 |
| Main | 5,000 | 50 | 300 | 164.14 | 166.16 | 152.36 |
| Q90 check | 5,000 | 11 | 33 | 17.36 | 19.14 | 152.35 |

The configuration pilot projected 132.76 seconds with a 20% planning margin.
Actual main execution remained below the 180-second target and 300-second hard
limit. Worker memory ceiling was 512 MiB. Read-only preparation peaked at
220.52 MiB. Pilot peak figures use worker self-measurement; the main and Q90
watchdogs also independently monitored the interpreter PID. Main aggregate output
was approximately 1.73 MB; individual presentation CSVs are below 150 KB.

Original study verification: 71 safe tests passed, three scenario sweeps excluded. Every run
conserves budget, closes reservations, reconciles all outcomes and has zero
routing/overrun. Within-replicate workload/cost-draw hashes and budgets match.
An independent audit reconstructs only 48 integer block choices per resample
(no policy reruns), verifies all 49 source-block sequences are distinct, and checks
their implied demand counts against saved results. Paired comparisons use the
correct FCFS run. All 55 protected existing files and both raw telemetry files
match their baselines; the historical results still contain 24 rows.

Presentation files: `policy_summary.csv`, `paired_effects.csv`,
`tenant_outcomes.csv`, `replicate_results.csv`, `sampling_audit.csv`,
`ranking_stability.csv`, `reservation_sensitivity.csv`, and the shared [provenance](../results/presentation/provenance.json).
`*_pct` columns are percentages; `*_pp` are percentage points; output totals
are tokens. `replicate_results.csv` labels replay separately with replicate 0.
The shared provenance records input and output hashes; the saved study plan records settings.

The versioned evidence under [results/monte_carlo/](../results/monte_carlo/) includes main and Q90 run-level records, tenant records, pairing hashes, scenario metadata, cap audits, sampling audit and runtime diagnostics. The exact [training](../results/monte_carlo/training.csv) and [evaluation](../results/monte_carlo/evaluation.csv) samples are also committed. The original ignored experiment directory remains untouched locally. Its internal `experiment_summary.csv` has legacy `ci95_*` columns; do not use them as real-world confidence intervals.

## Saved-table reproduction (safe)

```bash
python tools/build_presentation.py
python -m pytest -q
```

The one presentation builder reads committed saved evidence, executes no simulation policies and verifies paired baselines and block-draw identities. It works without raw telemetry or `outputs/`. The shared [dictionary](../results/presentation/data_dictionary.md) defines every column, including the renamed `completed_requests`, `truncated_requests` and `rejected_requests` in the replicate export.

## Optional experiment reproduction (expensive; not routine verification)

The fixed sample is sufficient to inspect the exact study population. To regenerate the original stratified selection from the full source, obtain both synthetic competition raw files described in [data/raw/README.md](../data/raw/README.md), then use these commands in a fresh working copy with empty destination directories:

```bash
python src/ironviz_experiments.py --openai data/raw/openai_pipeline_telemetry_raw.csv --gemini data/raw/gemini_pipeline_telemetry_raw.csv --prices config/prices.csv --out outputs/reproduction_telemetry
python tools/adapt_reference.py --clean outputs/reproduction_telemetry/clean_requests.csv --simulation outputs/reproduction_telemetry/requests_sim.csv --output-dir outputs/canonical_reference
python tools/run_october_monte_carlo.py prepare
python tools/run_october_monte_carlo.py run --stage tiny --replicates 3
python tools/run_october_monte_carlo.py run --stage pilot --replicates 3
python tools/run_october_monte_carlo.py run --stage main --replicates 50
```

Only if the measured main stage finishes below its planning target, the optional Q90 check is `python tools/run_october_monte_carlo.py run --stage quantile --replicates 11`. The runner refuses existing stage directories, limits workloads to 8,000 events per policy run, sets a 512 MiB worker ceiling and a 300-second hard stage deadline, and checks pilot measurements before main. None of these experiments was rerun during repository consolidation. The generator still writes to ignored `outputs/`; the published saved evidence is never overwritten by these commands. To compare a new run with the published study, inspect it separately rather than copying it over `results/monte_carlo/`.

The completion-median, paired-effect, cap, ranking and sensitivity claims above were verified directly against the saved CSVs during consolidation. The original experiment's 71-test verification is historical; the current cleanup checks and preservation decisions are recorded in [CLEANUP.md](CLEANUP.md). No full-data corrected evaluation or legacy sweep was run.
