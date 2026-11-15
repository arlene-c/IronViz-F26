# Monte Carlo findings

This completed exploratory component asks whether a policy difference in one
fictional replay persists when workload blocks change. It uses saved outputs;
no experiment was rerun for presentation. Download the [summary](../results/presentation/monte_carlo_pilot_summary.csv)
or [all replicate records](../results/presentation/monte_carlo_pilot_replicates.csv)
directly from GitHub.

## What was random, and why

The pilot uses 2,000 synthetic requests: 400 training and 1,600 evaluation. It
compares FCFS, Adaptive and Pacing in 90 small runs: replay plus 29 resamples.
Local 12-hour blocks are sampled within +/-3 days, then retimed to target blocks.
This changes the workload composition and order while retaining within-block
records. It tests sensitivity to a single observed synthetic request sequence.

All policies in a replicate receive identical sampled requests and cost draws.
Paired differences subtract FCFS on that SAME workload. Replay is replicate 0
and excluded from every resample summary. Training and policy parameters stay
fixed; routing and estimator-noise perturbations are zero. The fixed seed is
20261114, with an explicit roster and horizon. Budgets are 70% of each sampled
workload's reference expenditure. Original runner time was 14.44 seconds.

## What the pilot found

| Policy versus FCFS | Replay | Resample median | Interquartile range | Wins / ties / losses |
|---|---:|---:|---:|---:|
| Adaptive | +0.625 pp | -0.125 pp | -0.438 to +0.313 pp | 11 / 2 / 16 |
| Pacing | +11.875 pp | +11.750 pp | +11.250 to +13.188 pp | 29 / 0 / 0 |

Adaptive's positive replay ordering reverses in 16/29 draws. Pacing remains above
both policies in the saved draws, but also produces more truncated executions.
The [mechanism investigation](PACING_INVESTIGATION.md) found no Pacing rule
mismatch in a tiny independent control. Pacing drops reservations exceeding the
current spending allowance; smaller requests can fit while larger ones cannot.
It does not queue or reorder requests, and it does not optimize useful output.

## What this does not establish

These are **exploratory synthetic outcome distributions**, not confidence
intervals for institutional effects or evidence of full-data policy superiority.
The fixture uses fictional scaled prices and uniformly spaced timestamps, with
no imposed October cost trend. Twenty-nine draws from one generated workload do
not cover training uncertainty, task utility, price uncertainty, other budgets
or other traffic regimes. Budgets vary with sampled reference costs, rather than
remaining fixed dollars. Mean reservations still truncate outputs without scarcity.

The historical October bootstrap probes are different: each method has ONE
resample plus replay. Use [their separate table](../results/presentation/bootstrap_methods_70pct.csv)
descriptively; do not pool them into this fictional pilot or label their two-point
ranges as confidence intervals.

The safe validation suite checks pairing, random streams, block structure,
training boundaries and prefix invariance. See [VALIDATION.md](VALIDATION.md)
and the [data dictionary](../results/presentation/data_dictionary.md).
