> Historical development specification; not the current implementation or result status. See README.md, METHODOLOGY.md and DATA_CONTRACT.md.

# ROLE
You are the lead simulation engineer for "The Cost of Scarcity" (CMU
research/visualization competition). Build, run, test, and document a modular
Python 3.11+ simulation backend. Work in the phases below. At each GATE, run
the stated commands, paste the real output, and fix failures before moving on.
Never report a result, test pass, or timing you did not actually execute.
Re-read this spec at the start of every phase.
The base raw data is stored under the folder data/

# SCOPE
I own ONLY simulation + optimization. A teammate owns data cleaning, pricing
research, calibration; another owns visualization. Everything must run on
deterministic synthetic fixtures now, and accept cleaned CSV/Parquet later
with no engine changes. You may edit files and run local installs/tests. Do
not push, deploy, or download external data.

# RESEARCH QUESTION
How should an institution allocate a limited generative-AI budget under
uncertain request costs, and when do adaptive or cost-reduction interventions
beat simpler admission policies? Investigate; do not assume sophistication wins.

# DATA LIMITS (never invent these)
No real spending limits, request utility/quality, user identity, reliable
latency, pre-execution completion tokens, or evidence that cheaper models
preserve quality. Tenant = billing/project group only. Label every budget,
eligibility mask, and routed outcome "modeled" or "counterfactual". Fixtures
are "SYNTHETIC TEST DATA", never CMU observations or real prices.

# PRE-REGISTERED HYPOTHESES (test; report nulls and reversals honestly)
H1 FCFS maximizes aggregate completions under mild scarcity but has the lowest
   minimum-tenant completion; quotas raise the floor at an aggregate cost.
H2 Adaptive sharing recovers most of quotas' aggregate loss while keeping
   most of the floor.
H3 A tuned cost-threshold baseline matches or beats adaptive/pacing on
   aggregate completions. (Falsifiable; do not rig tuning.)
H4 Routing gains rise with eligibility rate and fall as the routed
   output-length multiplier rises.
H5 Conservative reservation reduces truncation but increases rejection.

# KEY SEMANTICS (implement exactly; log any deviation in ASSUMPTIONS.md)
- Money: integer micro-USD. Prices stored as micro-USD per 1M tokens.
  cost = ceil(tokens * price / 1e6) per component (uncached input, cached
  input, output). Test boundaries. Cached tokens are a subset of input.
- Eligible workload: rows with original_status == success and valid token
  counts. Others are excluded from demand and counted in metadata.
- Reference cost R_ref = modeled cost of replaying eligible requests on their
  original models under the configured price table (NOT a real bill).
  Global budget B = f * R_ref, f in a configurable sweep (0.5,0.7,0.85,1.0).
  Budget horizon = full workload span; optional periodic reset is a config flag.
- Reservation R for a request = input_cost + out_price * min(Yhat, K_model),
  where Yhat comes from the estimator (mean or quantile q) and K_model is a
  configured output cap. reservation_mode in {mean, quantile(q), cap}.
- STRICT mode (default): if input_cost > R -> reject. Else allowed output =
  floor((R - input_cost)/out_price). If true Y <= allowed -> COMPLETED; else
  TRUNCATED, billed at the allowed amount. Spend never exceeds the ceiling.
  Settle: release surplus. SOFT mode: allowed = K; charge realized; record
  overspend explicitly.
- Outcomes (one terminal outcome per request): REJECTED, COMPLETED_ORIGINAL,
  TRUNCATED_ORIGINAL, COMPLETED_ROUTED_CF, TRUNCATED_ROUTED_CF. Headline
  completion reports original-model completions separately from routed ones;
  never merge them silently. No quality claims anywhere.
- Concurrency: none. Settlement is immediate. Optional `in_flight_window`
  (default 0, off) may hold reservations across N subsequent events as an
  explicit scenario assumption; document that it is not empirically grounded.
- Randomness: numpy SeedSequence with fixed integer spawn keys, never hash().
  Separate streams: workload, cost, routing. Per-request routing/cost draws
  are PRECOMPUTED per scenario as arrays keyed by request index, so every
  policy sees identical draws regardless of decision order (paired design).

# INTERFACE-LEVEL LEAKAGE PREVENTION
- `FullRequest` (frozen): realized output_tokens, realized cost, etc. Held
  only by the engine.
- `PreAdmissionView` (frozen, slots): request_id, timestamp, tenant, provider,
  model, input_tokens, cached_input_tokens (if observable; flag in config),
  configured prices, estimated cost. No realized fields.
- `ObservableState`: immutable snapshot (global remaining, per-tenant
  remaining/spent, historical spend, counts). No future data.
- Estimators and pacing curves are fit ONLY on a configured training window
  or online expanding history via `fit(history)` / `update(outcome)`; the
  engine feeds them past outcomes only. Evaluation uses the post-training
  window (or expanding-window for the whole run; document which).
- Tests: (a) introspect view/state fields against a forbidden-name list;
  (b) METAMORPHIC: perturb all requests after time t; all decisions at or
  before t must be identical.

# POLICIES (common interface: reset(cfg), decide(view, state), observe(outcome, state))
A. FCFS: admit iff R <= global remaining.
B. Quotas: quota_i = w_i * B (equal or configured weights); admit iff R <=
   tenant remaining and global remaining. No borrowing.
C. Adaptive sharing: protected_i = w_i * B. Tenant spends own balance first.
   Lender j's lendable amount = max(0, protected_j - spent_j - reserve_j(t)),
   reserve_j(t) = max(rho * protected_j * (1 - t/H),
   trailing_window_run_rate_j * (H - t)). Loans are debited from the lender
   immediately in the ledger (no double promising). Parameters: rho, window,
   max_borrow_fraction. Uses only past spend + current observable state.
D. Pacing: admit iff cum_spend + R <= B * (S*(t) + slack), where S*(t) is a
   cumulative target curve (linear, or from training-window aggregate
   demand). Unspent allowance carries forward. Deterministic given inputs.
E. Cost-threshold baseline: reject if R > tau (tau tuned on training window;
   optionally a per-tenant tau). Simple strong baseline for H3.
F. Routing wrapper composable with any of A-E: eligibility mask (global
   probability or per-tenant/size rules, as an explicit scenario parameter),
   model compatibility map, trigger rule (always, or when budget pressure
   > theta). Routed view uses the cheaper model's prices; the inner policy
   decides on the routed view. Routed outcomes: Y' = Y * m, m ~ LogNormal
   (mu_pair, sigma_pair) (configurable defaults, labeled assumptions); input
   tokens unchanged (documented assumption). Trace must carry both
   `observed_original_output_tokens` and `modeled_routed_output_tokens`.
Compare at least: FCFS, Quotas, Adaptive, Pacing, Threshold, FCFS+routing,
Adaptive+routing.

# OPTIMIZATION BENCHMARKS (offline, NOT deployable; label "hindsight")
1. Max-count benchmark: admit cheapest realized-cost requests until B is used.
2. Max-min tenant completion via water-filling or scipy LP (if justified).
Report each policy's gap to these. Tune policy hyperparameters on the
training window only, with equal tuning effort per policy; evaluate on test.

# EXPERIMENTS
- Replay (observed workload) and day-block bootstrap (resample whole days
  with replacement, preserving tenant mix and intra-day structure; document).
  Tenant-composition sensitivity via volume reweighting.
- Grid: budget fraction x demand imbalance x estimator noise x routing
  eligibility x reservation level. Defaults small for fixtures, configurable.
- Paired differences per replicate vs FCFS; percentile CIs; win rate; effect
  size. State plainly that intervals reflect workload resampling and modeled
  assumptions, not real-world cost uncertainty. No "Pareto-superior" claim
  unless metrics support it on all stated axes (tolerance in config).
- Fixture generator: heavy-tailed sizes, bursty tenants, >=2 providers,
  >=3 models, one planted heavy tenant so policy differences are testable.

# METRICS
Admitted, completed (original / routed), rejected, truncated, rates; realized
cost, reserved, unused, overrun; cost per completed request; per-tenant
admission/completion; min tenant completion; max-min gap; Jain and Gini over
per-tenant completion rates; token-weighted and cost-weighted served share;
completion by request-size quartile; spend share vs demand share by tenant;
time-to-budget-exhaustion; improvement vs FCFS. Never call request count
"utility" or "quality."

# OUTPUTS (document every column in DATA_CONTRACT.md, input + output sections)
event_traces.parquet (full traces only for scenarios flagged trace=true,
default: replay + one bootstrap rep; partitioned by scenario), budget_
timeseries.parquet (downsampled, all runs), run_metrics.csv, tenant_metrics.csv,
experiment_summary.csv, policy_comparisons.csv, regime_map.csv (policy
advantage over FCFS across scarcity x imbalance x uncertainty),
scenario_metadata.json, findings.md (hypothesis verdicts incl. nulls).
Trace fields: run_id, scenario_id, seed, timestamp, request_id, tenant,
original_model, selected_model, policy, decision, outcome, estimated_cost,
reservation_before, reservation_after_settlement, realized_cost, global_
remaining, tenant_remaining, cumulative counts, is_counterfactual flag.
Diagnostic Matplotlib charts: completion vs budget fraction, per-tenant
completion, budget remaining over time, paired differences with CIs, routing
sensitivity to eligibility. Diagnostic only; no styling work.

# INPUT ADAPTER
CSV/Parquet with: request_id, timestamp, provider, model, tenant,
input_tokens, output_tokens, cached_input_tokens, original_status, optional
reference_cost. Validate columns, types, uniqueness, cached <= input,
non-negative tokens, chronological order. Emit a row-level error report
(never silently drop). No raw-JSON parsing.

# PHASES AND GATES
P1 schemas, money, pricing catalog (versioned), estimators (global,
   model-conditional, quantile), ledger, input adapter. GATE: unit tests green.
P2 engine, trace, FCFS, Quotas, fixture generator, leakage + determinism +
   reconciliation tests. GATE: pytest green; FCFS end-to-end on fixture.
P3 Adaptive, Pacing, Threshold, routing wrapper, hindsight benchmarks;
   handcrafted-scenario decision tests. GATE: pytest green.
P4 experiment runner, bootstrap, stats, output writers, CLI (generate-
   fixture, validate-data, run-simulation, run-experiments, generate-report).
   GATE: all CLI commands run on the fixture; outputs match DATA_CONTRACT.
P5 diagnostics, findings.md, docs (README results-first with quickstart,
   ARCHITECTURE, ASSUMPTIONS, DATA_CONTRACT), Makefile, CI workflow, license,
   committed SMALL sample outputs. GATE: fresh-venv install + full run.

# REQUIRED TESTS (pytest)
No-future-info (incl. metamorphic); determinism; zero budget -> zero billable;
test-4 rewritten: with reservation_mode=cap and budget >= sum of all
reservations, baseline completes every eligible request; strict never
overspends; cached-token cost; reserve/settle reconcile; tenant totals =
global; one terminal outcome per request; identical workload and draws across
policies; routing explicitly changes cost + outcome labels; no quality
equivalence assumed; clear validation errors; boundary values (budget ==
cost, cost +-1 micro-unit); handcrafted expected decisions; adaptive never
double-promises budget. If an invariant conflicts with a scenario assumption,
document the exception and write the alternative test.

# PERFORMANCE
Target: 200K requests/policy-run in under ~30s on a laptop, O(1) per
decision, numpy arrays/itertuples, no per-row pandas indexing. Measure and
report actual timings.

# FINAL REPORT
Files created; algorithms; commands run with real output; test results;
measured performance; example results labeled FIXTURE; hypothesis verdicts;
methodological limitations; exactly what the data teammate must supply
(schema, price table with source/date, training/test split, budget
assumptions, eligibility and routing-outcome assumptions).