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
