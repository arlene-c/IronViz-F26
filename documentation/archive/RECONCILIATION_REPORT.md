# Reconciliation Report

## Scope

This report separates the committed data-team simulator from the modular strict-budget engine. The legacy source/results are preserved and were not overwritten. The full request-level compatibility replay is being rerun after aligning its output cap to the legacy no-truncation behavior; until that rerun completes, its request-divergence table is not considered final.

## Data and Pricing

The committed cleaner reports 202,650 original rows, 192,847 eligible rows, and 9,803 exclusions (5,672 HTTP 400, 4,124 HTTP 429, seven invalid negative reasoning-token records). The cleaned-to-simulation adapter verified exact one-to-one eligible request coverage and stable request ordering.

The legacy reference cost is USD 5,710.443150 from its floating USD calculation. Canonical component-level integer micro-USD ceiling arithmetic yields 5,710,576,193 micro-USD = USD 5,710.576193. Difference: USD 0.133043 (0.0023298%). This is expected per-component rounding, not missing demand.

The pricing file records source URLs but not effective dates. The provider map resolves five model names to one observed provider each. Configured downgrade pairs are:

- OpenAI `gpt-4o` to `gpt-4o-mini`.
- OpenAI `o1-preview` to `gpt-4o`.
- Gemini `gemini-1.5-pro` to `gemini-1.5-flash`.

## Legacy Reference Run

The committed legacy `results.csv` reports run-0 FCFS admission of 100.0%, 82.493%, 65.307%, and 44.620% at 100%, 85%, 70%, and 50%, respectively. Its same-run output is preserved under `results/` and is a reference, not the modular strict-budget result.

A preliminary compatibility replay used the committed expected costs and disabled routing. It identified early differences from float-to-micro rounding and accumulated realized-cost settlement; however, that first run used the modular default output cap and therefore could introduce truncation absent from the legacy implementation. It is superseded by the pending corrected compatibility run and must not be used for final divergence claims.

## Semantic Differences

| Dimension | Legacy reference | Modular authoritative engine |
|---|---|---|
| Cost units | Floating USD, accumulated | Integer micro-USD; each component ceiled |
| Estimate | Prior tenant/model median; first observation falls back to current output | Training-only model mean/quantile/cap or a documented online prior; no current/future output access |
| Admission | Expected-cost admission | Explicit modeled reservation, strict global ceiling by default |
| Settlement | Full realized charge; self-check allows up to 1% spend above budget for FCFS/routing | Request reservation, exact settlement; strict mode does not overspend |
| Quotas | Full-month realized-spend share by default, or even split | Equal or training-window spend-calibrated weights; separately labeled |
| Adaptive | Idle-budget borrowing against remaining-month quota pace | Protected balances, reserved lender debits, borrower borrow cap, trailing-window run rate |
| Routing | Fixed token lengths and configured price downgrade | Explicit eligibility and compatibility, modeled output-length multiplier, separate `_ROUTED_CF` outcomes |
| Bootstrap | 12-hour blocks sampled within ±3 days, retimed | Day-block default; data-team local 12-hour ±3-day method is separately configurable |

## Reconciliation Categories

Final first-divergence classifications will be generated after the corrected compatibility replay completes. The intended categories are implementation/order errors, input/reference mismatch, per-component rounding, integer budget conversion, estimate differences, settlement differences, output-cap/truncation semantics, or expected policy differences. No compatibility mode changes canonical strict mode.

## Provenance

All input rows, prices, and results originate from files committed on `origin/main` at `a6cf13e`; raw telemetry was not edited. Modular compatibility and authoritative outputs are written under ignored `outputs/` paths. See `INTEGRATION_AUDIT.md` for source-level findings.
