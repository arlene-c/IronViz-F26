# The Cost of Scarcity

CMU Student IronViz Fall 2026: how do admission rules allocate a limited AI
inference budget across operational tenants? Inputs are 202,650 **synthetic**
OpenAI/Gemini telemetry records from October 1-30, 2026; 192,847 are eligible.

## Results teammates can use immediately

Download [results/canonical](results/canonical/) from the integration branch.
[VISUALIZATION_HANDOFF.md](VISUALIZATION_HANDOFF.md) identifies columns, joins,
units and limitations. No simulator run is needed to make figures.

The preserved six-policy evaluation uses 154,278 requests after 38,569 training
requests. At a modeled 70% evaluation budget ($3,079.115819):

| Policy | Fully completed originals |
|---|---:|
| FCFS | 42,573 |
| Equal quotas | 36,641 |
| Training quotas | 44,699 |
| Adaptive | 45,768 |
| Pacing | 46,217 |
| Threshold | 47,384 |

These are **pre-correction, provisional simulation results**, not outputs from
repaired code. Admission includes truncated executions. A 1,024-token cap and
mean reservations cause 105,693 truncations even at 100% reference budget.
Equal quotas strand $741.27 at 70%; Adaptive recovers capacity but engineering
loses 1,900 completions versus FCFS. Each bootstrap set contains only one
resample plus replay: no defensible confidence intervals. Routing quality is
unmeasured and no routed policies are in this comparison.

The descriptive summaries show o1-preview is 5.33% of eligible calls and 50.73%
of modeled cost. Cache/model mix changes differ by tenant; these patterns do
not establish learning or causal savings. Full-month modeled reference cost is
$5,710.576193. Price effective dates are unavailable.

## Install and verify safely

Python 3.11+; create a virtual environment, then:

```bash
python -m pip install -e .
python -m ironviz_f26 --help
python -m pytest -q
```

For a small synthetic example (fictional prices; not competition evidence):

```bash
python -m ironviz_f26 generate-fixture --requests 16 --output outputs/smoke/requests.csv --price-catalog-output outputs/smoke/prices.json
python -m ironviz_f26 validate-data --input outputs/smoke/requests.csv --error-report outputs/smoke/errors.csv
python -m ironviz_f26 run-simulation --input outputs/smoke/requests.csv --price-catalog outputs/smoke/prices.json --output-dir outputs/smoke/result --policy FCFS --data-label "SYNTHETIC TEST DATA"
```

Full-data experiments, bootstrap sweeps and routing grids are expensive and are
not part of installation or safe verification. Do not rerun them to obtain the
published tables. Existing inputs can be adapted with `tools/adapt_reference.py`;
its help documents paths. `tools/curate_results.py` copies completed aggregates
only, checks reconciliation/hashes, and never executes policies.

## Repository map

| Path | Role |
|---|---|
| `ironviz_f26/`, `tests/` | Modular strict-budget backend and synthetic unit tests |
| `results/canonical/` | Curated historical outputs, configuration and provenance manifest |
| `documentation/DATA_CONTRACT.md` | Authoritative machine schema |
| `METHODOLOGY.md` | Accounting, corrections and historical caveats |
| `documentation/SPEC.md`, `documentation/archive/` | Original development specification and historical audits |
| `src/`, `config/prices.csv`, `run_all.sh` | Preserved data-team analysis pipeline and pricing assumptions |
| `results/analysis_*.csv`, `figures/`, `charts/`, `docs/ALT_TEXT.txt` | Preserved legacy analysis and visuals; not corrected modular results |
| `outputs/` | Ignored local full traces, experiments and scratch artifacts |
| `data/raw/` | Local raw CSVs; not included in the integration branch tree |

Timed policies require explicit `--horizon-start` and `--horizon-end`;
`--tenant-roster` overrides a training-only tenant roster. Full schemas and
post-correction definitions are in the data contract. Scenario-sweep tests are
excluded by default; do not enable them during finalization.

The original `bash run_all.sh` regenerates legacy results/figures and is an
expensive workflow, not a quickstart. Its soft-budget semantics, retrospective
quota weights and first-observation estimate differ from the modular engine.
Original charts remain intact and contain legacy conclusions; do not relabel
them as modular results. See methodology and handoff before reusing titles/alt text.

## Data and provenance

Raw telemetry and caches were already committed in upstream history. Finalization
stops tracking their current copies without deleting local inputs or rewriting
shared history; this does not remove historical Git objects. Large legacy cleaned
outputs already tracked by the team are preserved. Never commit new raw copies,
full event traces, credentials, environments or scratch experiments.

Pricing citations are in `config/prices.csv` and the curated configuration;
OpenAI: https://developers.openai.com/api/docs/pricing ; Gemini:
https://ai.google.dev/gemini-api/docs/pricing . No real answer utility, demographic
identity or quality-equivalent routing claim is supported. AI-assisted analysis
and engineering require human review; preserved original work remains attributable
through Git history.
