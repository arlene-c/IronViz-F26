# Integration Audit

## Scope and Git Provenance

- The protected modular snapshot is commit `4c20ac9` on `simulation-backend`.
- The integration branch `simulation-integration` is based on teammate `origin/main` commit `a6cf13e`; earlier history includes `e3289e3`.
- The committed data-team implementation is retained at `src/ironviz_experiments.py`, with `config/prices.csv`, `run_all.sh`, `charts/`, `results/`, `figures/`, and `data/raw/` preserved.
- No raw telemetry or legacy result/figure file was modified by the integration steps. Generated integration artifacts are under ignored `outputs/` paths.

## Confirmed Data Claims

The committed `results/settings.json` reports 202,650 total rows, 192,847 used rows, and 9,803 exclusions: 5,672 HTTP 400, 4,124 HTTP 429, and seven negative reasoning-token records. The committed baseline reference total is USD 5,710.44. The committed pricing CSV has five model rows and provider citation URLs but no effective dates. The source lists retired model price assumptions and identifies Gemini cache scope as prompts up to 128k.

The committed reference result file reports, for run 0, at 70% budget: FCFS 65.307% admitted, quotas 61.325%, adaptive 61.325%, and routing 100% with 10.591% downgraded. These are legacy-model outputs, not validated quality-equivalent service outcomes.

## Source Audit

| Area | Confirmed implementation | Caveat / unconfirmed claim |
|---|---|---|
| Cleaning/exclusions | Provider-specific JSON usage parsing; stable timestamp/request ordering; keeps `exclude_reason`; excludes missing/unknown model, invalid usage/tokens, out-of-window rows, failed HTTP status | The raw files are team-labeled synthetic logs, not independently verified institutional observations |
| Provider mapping | OpenAI `prompt_tokens`, `completion_tokens`, cached prompt tokens, and reasoning tokens; Gemini `promptTokenCount`, `candidatesTokenCount`, cached content count | Gemini reasoning tokens are unavailable/NaN in the source parser; reasoning tokens are not added as a separate billed component |
| Price mapping | Five model rows; USD per 1M tokens; source URL per model; cheaper-model column | No price effective date is recorded. Retired-model prices and Gemini input/cache tier applicability are not independently validated |
| Cached-token accounting | Legacy price formula charges uncached and cached input components separately | Legacy costs remain floating USD and are accumulated without per-component integer-micro-USD ceiling |
| Output estimate | Online mode uses earlier tenant/model outputs through expanding median and shift | First observation falls back to that group’s first realized output, leaking the current request’s output into its own estimate; month mode uses the whole month and leaks future outputs |
| Reference cost | Sum of floating realized original-model costs in the legacy `Arrays.real` values | Differs from canonical componentwise micro-USD rounding, quantified in `RECONCILIATION_REPORT.md` |
| Budget accounting | Admission uses expected-cost float; ledger charges full realized float. FCFS/routing self-check allows up to 1% spend above budget | Not strict budget reservation/settlement. Fixed quotas/adaptive may not share the same overspend guard |
| Quotas | Default quota shares are full-month realized cost shares; alternative is even shares | Spend-derived shares are hindsight, not deployable training estimates |
| Adaptive | Idle-budget borrowing based on remaining-month linear quota pace | Differs from modular protected-reserve/lender-debit borrowing; algorithms are not treated as equivalent |
| Routing | Uses `cheaper_model`; downgrades on pace-ahead or original expected cost not fitting; preserves original token lengths in downgraded cost | Fixed-token, cost-only counterfactual. No task quality or quality-preserving eligibility evidence |
| Bootstrap | Seeded `default_rng`; 12-hour slots, blocks sampled from within ±3 days, then retimed to target slot | Reproduced workload sampler is retained as a separate integration method. It is not a forecast and is not the same as whole-day bootstrap |
| Self-checks | Checks same-seed adaptive decisions, daily spend reconciliation, no refuse-and-downgrade overlap, and FCFS/routing overspend <=1% | Does not cover leakage on the first observation, strict budget bounds, or full policy-level budget/tenant reconciliation |
| Visualization | Static and animated chart scripts, data files, and figures are committed | Several charts/readme conclusions describe legacy outcomes; their numbers/titles must not be relabeled as modular results |

## Adapter Verification

`tools/adapt_reference.py` consumed the committed cleaned CSVs and pricing CSV. It accepted exactly 192,847 of 192,847 eligible rows, retained a separate 202,650-row provenance table, and generated a micro-USD catalog and route map. No raw parsing or raw data edits were performed.

Price units were converted using decimal arithmetic: USD per 1M tokens multiplied by 1,000,000 to obtain integer micro-USD per 1M tokens. Configured routes were checked against componentwise prices.

## Cost Reconciliation

Canonical component-level ceiling arithmetic totals 5,710,576,193 micro-USD (USD 5,710.576193). The legacy `requests_sim.csv` unrounded total is USD 5,710.443150. Difference: USD 0.133043, or 0.0023298% of the legacy total. This is the expected precision difference from per-request/per-component ceiling versus floating accumulation, not an unexplained missing row.

## Methodological Status

The modular engine is authoritative for strict-budget modeled decisions. The legacy output is a reference implementation only. Routed completions remain counterfactual and are never described as quality-equivalent. No current result establishes actual institutional savings or quality-preserving feasibility.
