# The Cost of Scarcity: Should CMU Ration AI, or Make It Cheaper?

**Who keeps access to AI when a shared budget runs short?** This CMU Student IronViz 2026 project combines synthetic OpenAI and Gemini telemetry with a strict-budget simulator to compare six allocation strategies. It shows how request costs, model choices and budget rules affect both overall service and access across six operational teams.

Limited budgets create competing objectives: complete more requests, protect each team's access, avoid idle allocations, and control spending. A higher completion count can conceal a team loss. Cheaper model substitutions introduce another question: what answer quality would users give up?

## What we found

- **Costs are concentrated.** o1-preview represents 5.33% of eligible calls but 50.73% of reconstructed expenditure in the synthetic month.
- **Locked allocations can waste capacity.** In the preserved historical 70% budget replay, Equal Quotas leaves $741.27 unused while rejecting 33,745 requests. Adaptive completes 3,195 more requests than FCFS, but engineering-dev loses 1,900 completions.
- **The corrected October subset study has a stable leading order.** Across 49 matched workload resamples, Threshold beats Pacing, and Pacing beats Adaptive, every time. Equal Quotas versus FCFS is much less stable.
- **Execution assumptions matter.** Conservative output reservations sharply reduce truncation and change the size of policy advantages.

The completed Monte Carlo study uses 5,000 October evaluation requests and a separate earlier training sample. At a modeled 70% budget:

| Policy | Median fully completed | Median paired gain over FCFS |
|---|---:|---:|
| First come, first served | 35.35% | reference |
| Equal Quotas | 35.49% | +0.26 pp |
| Training Quotas | 39.36% | +3.93 pp |
| Adaptive sharing | 40.22% | +4.87 pp |
| Spend pacing | 45.46% | +10.16 pp |
| Cost threshold | 47.63% | +12.30 pp |

These are **modeled outcomes on synthetic competition telemetry**, conditional on one subset, budget and reservation setting. They do not establish a universal winner or actual CMU performance. Historical replay results precede correctness repairs and use different assumptions; keep them separate from this study.

## Dataset and approach

The source contains **202,650 synthetic API records from October 1-30, 2026**. After exclusions, **192,847 successful requests** are eligible across six tenants and five models. Full-month component-rounded reference expenditure is $5,710.576193; it is a modeled list-price reconstruction, not an invoice.

The project connects four layers:

1. **Telemetry and descriptive analysis:** reconcile usage fields, exclusions, premium-model concentration, cached input and calendar trends.
2. **Event-driven allocation:** compare FCFS, Equal Quotas, Training Quotas, Adaptive, Pacing and Threshold with explicit reservations, settlements and integer micro-USD accounting.
3. **Counterfactual routing:** model eligible cheaper-model substitutions with explicit compatibility and output-length assumptions. Quality equivalence is not measured; routing is disabled in the headline comparisons.
4. **Paired Monte Carlo analysis:** resample local 12-hour workload blocks and give every policy the same requests and budget. Train estimates and calibrated parameters using only the earlier training window.

Admission authorizes execution; a request can then truncate. **Full completion** means delivering its entire original output, which still does not measure answer quality or task usefulness.

## Explore the project

Start with the [visualization handoff](VISUALIZATION_HANDOFF.md) and [chart-ready datasets](results/presentation/). No simulation is needed to make the final figures. One [data dictionary](results/presentation/data_dictionary.md) defines units, denominators and joins; [provenance](results/presentation/provenance.json) records saved inputs and output hashes.

The existing [interactive story](figures/story.html) and [dashboard](figures/dashboard.html) explore descriptive telemetry, the **historical pre-correction replay**, and the separately labeled **corrected Monte Carlo study**. Download/open the HTML locally to interact; GitHub's file view displays source. The handoff provides seven chart specifications, including the reservation sensitivity.

![Six teams differ in prompt size, premium-model use and caching.](figures/static/04_team_fingerprints_2D.png)

The [descriptive static figures](figures/static/) support the usage narrative. Outdated admission/routing graphics were removed rather than presented as strict full-completion evidence.

## Repository guide

| Path | Purpose |
|---|---|
| `results/presentation/` | Single entry point for all final chart-ready CSVs |
| `results/canonical/` | Frozen historical six-policy results and original manifest |
| `results/monte_carlo/` | Exact study samples, saved aggregates, configuration and cap audits |
| `results/analysis_*.csv` | Descriptive source summaries used by active chart builders |
| `ironviz_f26/` | Current simulation, accounting, routing and experiment backend |
| `src/`, `config/` | Telemetry preparation and price assumptions |
| `charts/`, `figures/` | Descriptive charts and interactive story/dashboard |
| `documentation/` | Methodology, contract, Monte Carlo report and cleanup record |
| `tests/`, `tools/` | Safe checks, saved-result aggregation and bounded research utilities |

The 25.9 MB cleaned telemetry remains tracked because the active story and descriptive chart builder use it. Raw records and regenerable simulation/exclusion intermediates remain local and ignored. See the inspected [cleanup manifest](documentation/CLEANUP.md) for removal and retention decisions.

## Run safely

Use Python 3.11+ in a virtual environment:

```bash
python -m pip install -e .
python -m pytest -q
python -m ironviz_f26 --help
python tools/build_presentation.py
```

The presentation command reads **versioned saved tables only** and executes no policies. It works from a fresh checkout without raw telemetry or ignored experiment directories. Scenario-sweep tests are excluded by default.

A small synthetic smoke test, separate from published results:

```bash
python -m ironviz_f26 generate-fixture --output outputs/smoke/requests.csv --price-catalog-output outputs/smoke/price_catalog.json --requests 24
python -m ironviz_f26 validate-data --input outputs/smoke/requests.csv
python -m ironviz_f26 run-simulation --input outputs/smoke/requests.csv --price-catalog outputs/smoke/price_catalog.json --output-dir outputs/smoke/fcfs --policy FCFS --budget-fraction 0.7
```

See [methodology and optional reproduction](documentation/METHODOLOGY.md) and the [Monte Carlo report](documentation/MONTE_CARLO.md) for research commands. Expensive reproduction is separate from routine verification.

## Interpretation

Telemetry is synthetic; prices lack verified effective dates. Reservations limit execution output as well as admission. The Monte Carlo distribution holds training estimates and the chosen subset fixed, so it does not cover all sources of uncertainty. Historical results are provisional and were not rerun with the corrected engine. Tenant comparisons concern operational groups, not demographic fairness. No result demonstrates quality-preserving routing or institutional savings. See the [methodology](documentation/METHODOLOGY.md), [Monte Carlo report](documentation/MONTE_CARLO.md) and [data contract](documentation/DATA_CONTRACT.md).

The repository combines the team's data analysis, visualization and simulation contributions. Analysis and engineering used AI assistance; scientific interpretation requires human review.
