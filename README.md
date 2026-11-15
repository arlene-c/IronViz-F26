# Intelligence at Scale: should CMU ration AI, or make it cheaper?

CMU Student IronViz, Fall 2026. Analysis of 202,650 synthetic OpenAI and Gemini API calls (Oct 1–30, 2026)
and a simulation of four budget rules for campus AI.

## Key findings
- Two testing teams (`org-engineering-dev`, `prj-ai-sandbox-testing`) make 33% of calls but use 45% of tokens.
  They barely cache (≈5% of calls vs 37–44%) and send ≈65–69% of calls to premium models.
- During October, the other four teams raised cache use from ≈17% to 55–69% of calls and cut premium-model
  use from ≈70% to 25–33%. The testing teams did not change.
- o1-preview is 5% of calls but ≈51% of estimated cost (≈$5,710 for the month at list prices).
- With 70% of October's budget, first come, first served serves ≈65% of requests and runs out around Oct 20;
  team quotas serve ≈62%. Routing expensive requests to cheaper models serves 100% by downgrading ≈20%
  (assuming the cheaper model's answer is acceptable; answer quality is not measured).

## Reproduce
```bash
pip install -r requirements.txt
# put the two competition CSVs in data/raw/ (see data/raw/README.md)
bash run_all.sh            # about 30 seconds with numba
```

## Repository layout
| Path | Contents |
|---|---|
| `src/ironviz_experiments.py` | Cleaning, pricing, descriptive datasets, Experiments 1–4, self-checks |
| `config/prices.csv` | USD per 1M tokens, downgrade targets, and a source for each price |
| `charts/` | Scripts that turn the results into the static and animated figures |
| `results/` | Experiment outputs, analysis tables, `settings.json`, `checks.txt` |
| `figures/static/` | Final PNG/SVG charts (alt text in `docs/ALT_TEXT.txt`) |
| `figures/animated/` | Animated version of the charts (open in a browser) |
| `data/raw/` | Where the competition files go (not committed) |

## Experiments
1. **Budget × policy**: FCFS, fixed quotas, adaptive sharing and smart routing at 100/85/70/50% of October's cost.
2. **Who loses access**: % served by team × request size (small <2k, medium 2k–10k, large >10k input tokens).
3. **Uncertainty**: 200 bootstrap months (12-hour blocks drawn within ±3 days, keeping October's cost trend).
4. **Noisy neighbour**: `org-engineering-dev` traffic ×3 on Oct 12–15 at an 85% budget.

## Method notes and limitations
- Rules decide with an **expected** cost (real input cost + median output of earlier requests for that team × model)
  and are charged the **realized** cost, so no rule sees the future.
- 9,803 rows are excluded and listed in `results/excluded_rows.csv`: 5,672 HTTP 400, 4,124 HTTP 429 (no usage,
  not billed) and 7 records with negative reasoning tokens.
- Prices are the last published list prices; these models are retired, and Gemini cache storage fees are not modelled.
- The data is synthetic: call volume is flat, there are no user IDs, and "fairness" means across operational
  tenants only, not demographic groups.
- Downgrade quality is assumed, not measured. The o1-preview → gpt-4o mapping is a team choice (`config/prices.csv`).

## Sources
- OpenAI model pricing: https://developers.openai.com/api/docs/pricing
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- OECD AI Principles: https://oecd.ai/en/ai-principles

## AI use
Analysis code was drafted with AI assistance and reviewed, run and validated by the team; see the
project documentation for prompts, decisions and checks.

## Modular simulation backend

The original `src/ironviz_experiments.py` pipeline, its committed results, and
the static/animated chart sources remain the legacy reference implementation.
The modular `ironviz_f26` package is the strict-budget research engine; its
counterfactual routed completions are reported separately and are not claims of
quality-equivalent service. Existing figures and hard-coded reference findings
describe the data team's legacy outputs, not the modular engine's results.

The backend accepts cleaned request CSV/Parquet files and a versioned price
catalog. Adapt the committed data-team outputs without modifying them:

```bash
python tools/adapt_reference.py \
  --clean results/clean_requests.csv \
  --simulation results/requests_sim.csv \
  --prices config/prices.csv \
  --output-dir outputs/canonical_reference
```

The integration adapter maps `cached_tokens` to
`cached_input_tokens` and converts the price CSV's USD-per-million values to
integer micro-USD-per-million. It does not parse raw provider JSON. The
authoritative input and output contracts are documented in
`documentation/DATA_CONTRACT.md`.

Run the modular backend after installing `requirements.txt`:

```bash
python -m ironviz_f26 validate-data \
  --input outputs/canonical_reference/canonical_requests.csv \
  --error-report outputs/canonical_reference/row_errors.csv
python -m ironviz_f26 run-experiments \
  --input outputs/canonical_reference/canonical_requests.csv \
  --price-catalog outputs/canonical_reference/price_catalog_micro_usd.json \
  --output-dir outputs/modular \
  --budget-fractions 0.5,0.7,0.85,1.0 \
  --reservation-mode mean
python -m ironviz_f26 run-experiments \
  --input outputs/canonical_reference/canonical_requests.csv \
  --price-catalog outputs/canonical_reference/price_catalog_micro_usd.json \
  --routing-compatibility outputs/canonical_reference/routing_compatibility.json \
  --output-dir outputs/routing-counterfactual \
  --budget-fractions 0.5,0.7,0.85,1.0 \
  --policies FCFS+Routing,Adaptive+Routing \
  --routing-eligibility 0.2,0.5,1.0 \
  --routed-output-multipliers 0.5,0.7,1.0
```

For the data team's 12-hour local-block bootstrap within a ±3-day window, add
`--bootstrap-method local_12h --bootstrap-block-hours 12 --bootstrap-window-days 3`.
`day_block` remains available for methodological sensitivity. For a strict
all-row FCFS replay with an expanding model-level historical estimate, use
`python tools/run_online_fcfs.py`. It starts each unseen provider/model with a
zero-output prior, so it avoids using the first row's realized output to price
its own reservation.

The original `bash run_all.sh` continues to regenerate the legacy reference
outputs. Do not use those soft-budget outputs as validated modular results;
compare them using `RECONCILIATION_REPORT.md` and the explicit cost/budget
semantics. Routed completions remain counterfactual and are never represented
as quality-equivalent service.
