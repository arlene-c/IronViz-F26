# Methodology and reproduction

The project separates descriptive telemetry, a preserved historical replay, and a corrected October subset Monte Carlo study. Their populations and execution assumptions differ. The [data contract](DATA_CONTRACT.md) defines simulator inputs and outputs; the [presentation dictionary](../results/presentation/data_dictionary.md) defines chart units and joins. The completed stochastic study is documented once in [MONTE_CARLO.md](MONTE_CARLO.md).

## Data and cost reconstruction

The competition provides 202,650 synthetic October 2026 records. The cleaner excludes 5,672 HTTP 400 calls, 4,124 HTTP 429 calls and seven negative reasoning-token records, leaving 192,847 eligible requests across six operational tenants. Cached input is a subset of total input, not an extra additive token count. Reasoning tokens are not separately added to the billed components.

The original descriptive reconstruction uses floating USD and totals $5,710.443150. The modular accounting ceilings each uncached-input, cached-input and output component to integer micro-USD, totaling $5,710.576193. The $0.133043 difference (0.0023298%) is expected rounding, not missing demand. Exact reconciliation and the price catalog are retained in [canonical configuration](../results/canonical/configuration/). Source prices lack effective dates and are modeled assumptions, not verified invoices.

Descriptive model/cost shares use eligible successful requests. Tenant call/error shares use operational records after removing invalid telemetry; they include failed calls. Weekly cache/premium shares use eligible requests. The six tenant labels are operational groups, not individuals or demographic categories.

## Allocation and execution

The current backend is [ironviz_f26](../ironviz_f26/). It implements FCFS; equal monetary quotas; training-spend quotas; adaptive protected borrowing; cumulative spending pacing; and a training-calibrated reservation threshold. Adaptive uses protected reserves, a trailing run-rate window and lender debits. Pacing releases budget over the configured horizon with 5% slack and rejects reservations that do not fit the current allowance. It does not queue, retry or reorder requests. Threshold is tuned for full training completions, then lower spending on ties.

Strict mode reserves before execution, limits output by both the selected-model cap and the funded reservation, then immediately settles and releases surplus. A rejected request receives no execution. An admitted request can truncate. Full original completion requires delivery of all original observed output, and does not imply useful or correct answers. Mean output reservations can therefore cause truncation even when total money is ample. Quantile and cap reservations are alternative execution assumptions, not merely admission estimates.

The routing framework additionally requires an explicit compatibility/eligibility assumption. Routed output lengths are counterfactual; input tokens are held unchanged. Original and routed completions remain separate, and cheaper substitutions are not assumed to preserve quality. Routing is disabled in the historical six-policy comparison and the corrected October study.

Model output distributions are fit using training only and keyed by provider/model; reservation overrides include request/provider/model. Explicit rosters and horizons make adaptive/pacing decisions independent of evaluation suffixes when the budget and estimator stay fixed. Budgets normalized to realized reference cost are retrospective scenario assumptions; changing the workload can change those budgets.

## Historical evidence and corrected semantics

[results/canonical](../results/canonical/) preserves the original manifest and pre-correction CSV values. The historical split is 38,569 training requests and 154,278 evaluation requests, October 7-30. Evaluation reference cost is $4,398.736885. Six policies at 50/70/85/100% budgets produce 24 runs. Each historical bootstrap method has replay plus **one** resample; no supported uncertainty interval follows from those probes.

At 70%, FCFS/Quotas/TrainingQuotas/Adaptive/Pacing/Threshold complete 42,573/36,641/44,699/45,768/46,217/47,384 requests. Equal Quotas leaves $741.272122, and Adaptive leaves $78.572794. Adaptive increases aggregate completions while engineering-dev loses 1,900 relative to FCFS. At 100%, FCFS admits all evaluation requests but completes only 48,585 and truncates 105,693. Cap/reservation effects cannot be described solely as scarcity losses.

These experiments preceded repairs: threshold calibration did not match strict evaluation settlements; rosters/horizons were inferred retrospectively; and mean reservations with a 1,024-token cap truncated extensively. Current code fixes integer arithmetic/catalog validation, provider/model lookup collisions, training threshold settlements and its reject-all candidate, UTC ordering, selected-target caps, reservation release and actual quota balances. It distinguishes cap/reservation flags, denial causes and true zero-balance exhaustion. Current cost-weighted served share counts original reference costs of fully completed originals; historical versions used spend/reference spend. Cost-per-completion includes wasted truncated execution spending, is null for zero completions, and is not a marginal cost. Routed hindsight gaps are suppressed when incomparable.

Replay and resample summaries are separate. Current summary interval fields are suppressed below 20 resamples; they remain conditional percentile summaries rather than institutional confidence intervals. Diagnostic aggregation does not average interval endpoints. Small tests verify strict calibration, lookup keys, paired streams, bootstrap structure, training boundaries, prefix invariance and denominators. These corrections do not retrospectively validate historical counts. No full-data corrected evaluation was performed.

The earlier fictional pilot and its development logs were superseded by the October study. A unique 50-request mechanism check remains in the [archived Pacing investigation](archive/PACING_INVESTIGATION.md): it found no admission-rule mismatch and showed how current allowance filtering can favor cheaper requests. The [original specification](archive/SPEC.md) preserves initial hypotheses and design intent; it is not a current implementation guide. Other redundant audits are recoverable from Git history.

## Routine verification and visualization

With Python 3.11+:

```bash
python -m pip install -e .
python -m pytest -q
python -m ironviz_f26 --help
python tools/build_presentation.py
```

The builder imports no simulation code and reads only committed saved evidence. It reconstructs 24 historical policy rows, 36 tenant rows, 24 historical method-probe rows, four descriptive exports, and the corrected Monte Carlo tables. It verifies matching FCFS baselines, paired seeds/demand/budgets, conservation, sampling block choices and source hashes. Tests also rebuild in a temporary fresh-checkout layout without ignored outputs or raw telemetry.

The interactive builders use the presentation tables, historical canonical trajectories and descriptive summaries, with separately labeled corrected Monte Carlo panels:

```bash
python charts/make_dashboard.py results charts/dashboard_template.html OUTPUT_DASHBOARD.html
python charts/make_story.py results charts/story_template.html OUTPUT_STORY.html
python charts/make_static.py results/clean_requests.csv OUTPUT_DIRECTORY
```

Use a separate output path; do not overwrite current figures during routine checks. The latest story/dashboard updates from remote commit 162622c were carried forward without a Git merge; their templates and rendered HTML are unchanged from that revision. The builders received explicit UTF-8 I/O fixes for Windows. The cleaned CSV remains tracked because those active workflows need it. Descriptive summaries keep established source paths; the presentation builder exposes their chart-ready equivalents in the single handoff directory.

## Optional data preparation and research reproduction

Raw telemetry remains local and ignored; obtain the two competition files using the [raw-data instructions](../data/raw/README.md). To reproduce cleaned/derived inputs and descriptive summaries without simulation:

```bash
python src/ironviz_experiments.py --openai data/raw/openai_pipeline_telemetry_raw.csv --gemini data/raw/gemini_pipeline_telemetry_raw.csv --prices config/prices.csv --out outputs/reproduction_telemetry
python tools/adapt_reference.py --clean outputs/reproduction_telemetry/clean_requests.csv --simulation outputs/reproduction_telemetry/requests_sim.csv --output-dir outputs/canonical_reference
```

The first command now stops after preparation by default. Simulation/exclusion intermediates are ignored, and their existing local copies were preserved. The legacy four-policy floating-budget implementation remains in that source file to explain the original pipeline; it requires explicit `--run-legacy-experiments` opt-in and is not the current engine. Do not use its first-observation estimator or full-month quota calibration as leakage-free policy estimates. Its old admission/routing charts, generated intermediates and redundant entry points were removed from the final narrative.

Optional expensive bounded October commands are isolated in [MONTE_CARLO.md](MONTE_CARLO.md). They were not executed during consolidation. The historical sweep, full-data evaluation, original fictional pilot, historical bootstraps and routing factorial were not rerun. Frozen canonical results are read-only evidence, not targets for regeneration.

## Limits

One synthetic month and one selected subset do not represent real institutional outcomes. Training and prices stay fixed under resampling; task utility, answer quality, concurrency and reliable latency are absent. Rare-model estimates can be noisy. Budget percentages scale to each workload's reference cost, not a constant-dollar institutional cap. Completion gains and token-delivery gains can disagree. Conditional resampling spreads describe the chosen model, not all scientific uncertainty. See [CLEANUP.md](CLEANUP.md) for verification and evidence-based repository decisions.
