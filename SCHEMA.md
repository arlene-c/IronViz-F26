# Data Architecture and Schema Guide

`DATA_CONTRACT.md` is the authoritative machine-readable interface reference: it defines the exact input and output columns, order, and file formats. This document explains how those records relate and which values are visible at each stage; it intentionally does not restate a competing column contract.

## Request Input

Cleaned requests are CSV or Parquet rows with unique `request_id`, chronologically ordered timestamps, provider/model identifiers, tenant billing/project group, integer input/output/cached-input token counts, and original status. `reference_cost` is optional and is never inferred by the adapter. See the input schema, types, nonnegative rules, and validation behavior in [DATA_CONTRACT.md](documentation/DATA_CONTRACT.md).

Provider and model values are opaque, case-sensitive strings. The simulation does not rename, normalize, or infer provider/model pairs. A request pair must match a catalog entry exactly; a route target must be an explicitly configured compatible pair. Tenant means billing/project group only, not an individual identity.

Only successful rows with valid token counts enter eligible simulated demand. Invalid rows are reported by `validate-data`; non-success statuses are excluded from eligible demand and counted in scenario metadata.

## Price Catalog and Money

The JSON catalog contains a version and rows keyed by `(provider, model)`. Input, cached-input, and output prices are integer micro-USD per one million tokens. Cached tokens are a subset of input tokens and are priced separately. Each component is rounded up to an integer micro-USD. The adapter does not research, verify, or assign a source/date to prices; those are supplied by the data teammate for cleaned empirical inputs.

The fixture command can write a synthetic catalog for reproducible software tests. It is explicitly fictional and must not be used as historical pricing.

## Engine and Policy Boundary

The input record contains observed realized output tokens and original request attributes. The engine retains this full request information and computes modeled billed cost, allowed output, and settlement. The current implementation accepts normalized `RequestRow` values or mappings; it does not pass those full records to policies.

`PreAdmissionView` is a frozen, slotted immutable object containing only current-request observable fields: request ID, timestamp, tenant, provider, selected model, input and cached-input token counts, input cost, output price, and estimated cost. It does not contain realized output tokens, realized cost, or future requests. Routed policies receive a view repriced for the configured target model. The inner admission policy never receives the original or modeled routed output length.

`ObservableState` is a frozen snapshot with global remaining budget and immutable per-tenant remaining/spent, historical spend, and counts. It contains no future request data. `decide(view, state)` returns the admission decision; `observe(outcome, state)` receives the terminal outcome and post-event state.

## Decisions and Outcomes

Admission decision is `ADMITTED` or `REJECTED`. A request has one terminal outcome:

- `REJECTED`
- `COMPLETED_ORIGINAL`
- `TRUNCATED_ORIGINAL`
- `COMPLETED_ROUTED_CF`
- `TRUNCATED_ROUTED_CF`

`_CF` outcomes are counterfactual routed simulations. Original-model and routed completions are reported separately; a combined count is provided only as an explicitly named aggregate count and is not a quality metric.

Adaptive sharing keeps protected tenant balances, lender debits, pending borrower reservations, and settled borrowed spend in policy state. Pacing uses a configured cumulative target curve and current elapsed fraction. Cost-threshold tuning receives explicit training reservations and freezes `tau` before evaluation. Routing eligibility and compatible model pairs are scenario settings. Model substitutions are checked against the configured catalog prices.

## Experiment and Output Relationships

A `run_id` identifies a policy run for one scenario, budget fraction, and replicate. `scenario_id` identifies the sampled workload and sensitivity settings used for paired policy execution. Within each run, `request_id` identifies the trace event. Resampled rows receive unique request IDs and retain `source_request_id` for joining to the original evaluation row. `tenant` joins tenant-level records to the billing/project group in the input.

- `event_traces.parquet` is the request-level decision and settlement ledger for trace-enabled runs.
- `budget_timeseries.parquet` contains downsampled post-event budget states for all runs.
- `run_metrics.csv` contains one aggregate row per run.
- `tenant_metrics.csv` contains one row per tenant per run.
- `policy_comparisons.csv` pairs non-FCFS results with FCFS using the same scenario, budget fraction, and replicate.
- `experiment_summary.csv` aggregates replicate-level results and percentile intervals across configuration dimensions.
- `regime_map.csv` groups average policy advantages over FCFS by budget scarcity, demand imbalance, and estimator-noise regime.
- `scenario_metadata.json` records input label, training/evaluation split, random stream keys, seeds, sample method, and explicit assumptions.
- `findings.md` reports pre-registered hypothesis verdicts, including inconclusive results.

The exact column definitions and diagnostic image names are maintained only in [DATA_CONTRACT.md](documentation/DATA_CONTRACT.md).

## Value Provenance

| Value class | Examples | Notes |
|---|---|---|
| Observed input | Request ID, timestamp, tenant, provider/model, token counts, original status | Supplied cleaned input or labeled synthetic fixture |
| Estimated | Estimated cost and reservation | Derived from training-window cost observations and configured sensitivity multiplier |
| Simulated | Admission decision, allowed output tokens, realized modeled cost, spend, remaining budget | Produced by the policy/engine under a modeled budget |
| Counterfactual | Selected routed model, modeled routed output length, `_ROUTED_CF` outcome | Scenario simulation only; not an observed completion or quality result |
| Hindsight | Max-count and max-min selected requests/rates | Offline benchmark using realized test-workload costs; not deployable |

## Examples

Valid synthetic request CSV row:

```csv
request_id,timestamp,provider,model,tenant,input_tokens,output_tokens,cached_input_tokens,original_status
req-0001,2026-01-01T00:00:00Z,openai,gpt-4o,tenant-a,1200,240,200,success
```

Catalog JSON row (synthetic values shown only to illustrate shape):

```json
{
  "version": "SYNTHETIC TEST DATA",
  "price_unit": "integer micro-USD per 1M tokens",
  "rows": [
    {
      "provider": "openai",
      "model": "gpt-4o",
      "input_price": 150,
      "cached_input_price": 40,
      "output_price": 250
    }
  ]
}
```
