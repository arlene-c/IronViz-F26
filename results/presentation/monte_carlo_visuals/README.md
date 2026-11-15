# Monte Carlo visuals

These charts are derived only from the corrected October Monte Carlo tables in
[`../monte_carlo/`](../monte_carlo/). They are a separate synthetic,
workload-resampling study and are not pooled with the preserved historical
October replay. The study has 300 policy runs: six policies on one replay plus
49 paired local-block resamples. Replicate 0 remains deliberately separate.

| File | What it shows |
|---|---|
| `12_monte_carlo_effect_distribution_2D.svg` | Every non-FCFS paired completion effect, the separate replay, and the resample IQR. |
| `13_monte_carlo_replay_vs_resamples_2D.svg` | Completion-rate distributions for all six policies alongside the original replay. |
| `14_monte_carlo_access_floor_2D.svg` | Aggregate completion against the lowest operational-tenant completion rate in every resample. |

The bars are interquartile ranges and all dots are saved simulation outcomes.
They are **not inferential confidence intervals** or real-world policy-success
probabilities. Completion counts and the operational-tenant access floor do not
establish task utility, demographic fairness, or policy quality.

Recreate the outputs with:

```bash
MPLCONFIGDIR=/tmp/matplotlib python3 make_monte_carlo_visuals.py
```

See [`../monte_carlo/README.md`](../monte_carlo/README.md) and its provenance
file for the study design, limits, and source revision.
