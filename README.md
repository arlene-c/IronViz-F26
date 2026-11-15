# The Cost of Scarcity

**Who keeps access to AI when the budget runs short?** This CMU Student IronViz
Fall 2026 project examines that question through synthetic OpenAI and Gemini
telemetry, modeled inference costs, and six allocation policies. It connects
usage analysis with an auditable simulator to show how a policy can increase
completed requests while shifting access between teams?or leave money unused
while requests are denied.

## The problem

An institution has a shared AI budget and teams with different request volumes,
model choices, and costs. Serving requests in arrival order is simple. Fixed team
allocations protect entitlements. Sharing, pacing, and cost thresholds make
different compromises. We compare **fully completed requests, access across
operational teams, and budget utilization**.

## The dataset

| Scope | Records |
|---|---:|
| Synthetic API telemetry, October 1?30, 2026 | 202,650 |
| Eligible successful requests | 192,847 |
| Operational tenants | 6 |
| Historical comparison: training requests | 38,569 |
| Historical comparison: evaluation requests | 154,278 |

These are synthetic competition records, **not actual CMU billing**. Full-month
modeled reference expenditure is **$5,710.576193**; the evaluation reference is
**$4,398.736885**. Neither is a verified invoice.

## Our approach

1. **Reconstruct cost:** price uncached input, cached input, and output separately.
2. **Compare allocation choices:** FCFS, equal quotas, training-calibrated quotas,
   adaptive sharing, pacing, and a cost threshold.
3. **Account explicitly:** reserve before execution, settle modeled costs, and
   distinguish completed, truncated, and rejected requests.
4. **Explore sensitivity:** compare policies on identical resampled workloads
   in a small, separately labeled synthetic Monte Carlo pilot.

## What the historical replay shows

At a modeled **70% evaluation budget ($3,079.115819)**:

| Policy | Fully completed requests | Unused modeled budget |
|---|---:|---:|
| First come, first served | 42,573 | <$0.01 |
| Equal quotas | 36,641 | $741.27 |
| Training-calibrated quotas | 44,699 | $101.37 |
| Adaptive sharing | 45,768 | $78.57 |
| Pacing | 46,217 | <$0.01 |
| Cost threshold | 47,384 | <$0.01 |

- **Equal budgets do not guarantee equal access.** Equal quotas leave $741.27
  unused while rejecting 33,745 requests.
- **Aggregate gains can conceal a team loss.** Adaptive adds 3,195 completions
  over FCFS, while engineering-dev loses 1,900.
- **A small request class dominates modeled cost.** Across the eligible month,
  o1-preview accounts for 5.33% of calls and 50.73% of estimated expenditure.

The policy table preserves **pre-correction, provisional experiment results**.
Mean reservations and a 1,024-token output cap cause substantial truncation even
at a 100% reference budget. These numbers describe modeled trade-offs; they do
not establish greater answer utility or the best policy for CMU.

## Why it matters

A policy can serve more requests by favoring cheaper executions, improve some
teams' access at another's expense, or protect allocations that remain unused.
An institutional decision needs more than one completion-count ranking. Our
results make those competing objectives visible.

## Results and visualizations

**Download individual CSVs from GitHub and build charts without running Python.**
Start with the [visualization handoff](VISUALIZATION_HANDOFF.md) for exact columns,
chart suggestions, joins, and caveats.

| Chart-ready dataset | What it supports |
|---|---|
| [Policy ? budget](results/presentation/policy_budget_summary.csv) | All 24 historical runs: outcomes, spending, unused money, FCFS differences |
| [Tenant trade-offs at 70%](results/presentation/tenant_tradeoffs_70pct.csv) | Winners and losers across six tenants and policies |
| [Bootstrap methods at 70%](results/presentation/bootstrap_methods_70pct.csv) | Separate replay and single-resample probes by method |
| [Monte Carlo summary](results/presentation/monte_carlo_pilot_summary.csv) | Paired medians, dispersion, wins/ties/losses, ranking reversals |
| [Monte Carlo replicates](results/presentation/monte_carlo_pilot_replicates.csv) | All 90 pilot runs: replay plus 29 resamples for three policies |

See the [data dictionary](results/presentation/data_dictionary.md) and
[source provenance](results/presentation/provenance.json). Original historical
exports remain unchanged in [results/canonical](results/canonical/).

The team's [static figures](figures/static/) and
[animated charts](figures/animated/animated_charts.html) preserve the original
presentation. Their simulation panels use the legacy pipeline, not corrected
modular results. A descriptive preview:

![Six teams differ in prompt size, premium-model use and caching.](figures/static/04_team_fingerprints_2D.png)

## Monte Carlo: a separate synthetic exploration

The completed pilot compares FCFS, Adaptive and Pacing on **29 paired workload
resamples plus a separate replay**, using 2,000 fictional source requests.
Pacing's median completion advantage is **+11.75 percentage points** over FCFS;
Adaptive's is **?0.125 points**, reversing its positive replay ordering in 16 of
29 draws. These are conditional synthetic outcomes, not full-data confidence
intervals or evidence of institutional policy superiority.

The [Monte Carlo findings](documentation/MONTE_CARLO.md) explain the design.
A [small mechanism investigation](documentation/PACING_INVESTIGATION.md) shows
that Pacing also selects among request costs: it drops requests exceeding the
current allowance rather than queuing them. More completions do not imply
more useful output.

## Repository guide

| Path | Purpose |
|---|---|
| `results/presentation/` | Chart-ready CSVs, dictionary and provenance |
| `results/canonical/` | Preserved historical outputs and configuration |
| `ironviz_f26/` | Modular budget simulation engine |
| `src/`, `config/` | Original preparation/analysis and pricing assumptions |
| `charts/`, `figures/` | Preserved visualization code and assets |
| `documentation/` | Methodology, contracts, validation and investigations |
| `tests/`, `tools/` | Safe checks and reusable utilities |
| `outputs/`, `data/raw/` | Ignored local experiment artifacts and raw inputs |

## Run the code safely

With Python 3.11+ in a virtual environment:

```bash
python -m pip install -e .
python -m pytest -q
python -m ironviz_f26 --help
```

Rebuild presentation aggregates from saved tables only:

```bash
python tools/build_presentation.py
```

That command executes **no simulation policies**. From a fresh checkout it uses
the published pilot replicate table to rebuild the pilot summary. Expensive
sweeps and the legacy `run_all.sh` are not part of the handoff workflow.
Scenario-sweep tests remain excluded by default.

## Methodology and limitations

See the [methodology](documentation/METHODOLOGY.md),
[data contract](documentation/DATA_CONTRACT.md), and
[correctness validation](documentation/VALIDATION.md). Historical experiments
preceded repairs and were not regenerated. Historical bootstrap probes have
one resample per method. Price effective dates, task utility and quality-preserving
model substitutions are unverified. Tenant disparity concerns operational groups,
not demographic fairness.

Raw files remain untracked and protected locally; some raw data already exists
in upstream Git history, which this work does not rewrite. Original teammate work
and attribution remain preserved. Analysis and engineering used AI assistance;
interpretations require human review.
