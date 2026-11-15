# Simulation Findings

Dataset label: **CLEANED REFERENCE INPUT; modeled strict-budget simulation**. All budgets and routed outcomes are modeled/counterfactual.
No result is a claim about request quality or equivalence between models.

Intervals describe workload resampling and modeled assumptions only; they are not real-world cost uncertainty.

## Pre-registered hypotheses

- INCONCLUSIVE: H1 aggregate/minimum-tenant direction: FCFS=41654.75/0.192; Quotas=38383.00/0.142.
- INCONCLUSIVE: H2 adaptive sharing recovers quota completions while retaining the floor.
- INCONCLUSIVE: H3 threshold completions=48113.75, adaptive=43081.75, pacing=47183.00.
- INCONCLUSIVE: H4 inconclusive: eligibility and output-length multiplier were not both varied.
- INCONCLUSIVE: H5 inconclusive: reservation multiplier was not varied.

## Interpretation limits

These results compare modeled request counts, costs, budget use, and tenant completion rates. Routed completions are counterfactual and are kept separate from original-model completions. Synthetic fixtures are SYNTHETIC TEST DATA, not CMU observations or real prices.
