# Why Pacing wins in the synthetic pilot

The prior validation fixes/tests were reviewed, committed as `a5106f9`, and pushed
only to `simulation-validation`. Safe tests: 63 passed, three scenario sweeps
excluded. Main and simulation-integration were not updated. This follow-up used
the saved pilot CSVs and one 50-request synthetic control. The 90-run pilot,
historical sweep, full-data experiments and bootstrap sensitivities were not rerun.

## Saved pilot observations

Sources: `outputs/monte_carlo_pilot/run_metrics.csv`, `policy_completion_rates.csv`.
The original replay has 1,600 evaluation requests and approximately equal spending:

| Policy | Fully complete | Truncated | Rejected | Admitted | Budget utilization | Input+output token-weighted served share |
|---|---:|---:|---:|---:|---:|---:|
| FCFS | 760 | 390 | 450 | 1,150 | 99.997% | 70.611% |
| Adaptive | 770 | 391 | 439 | 1,161 | 99.993% | 70.037% |
| Pacing | 950 | 473 | 177 | 1,423 | 100.000% (rounded) | 70.856% |

Pacing's +190 completions (+11.875 percentage points) come with 83 more
truncations and 273 fewer rejections. Its average spend per admitted execution is
158.15 micro-USD versus FCFS 195.68: the admitted mix is less expensive.
`cost_weighted_served_share` rises only from 44.343% to 45.754%, while the combined
token share rises only 0.245 percentage points. Request-count gains are much
larger than gains in these demand-volume measures.

Resample medians (29 draws, separate from replay): FCFS 761 completed, 390
truncated, 453 rejected; Adaptive 759/391/458; Pacing 949/478/170. These are
separate column medians, not one common representative replicate. The median
paired Pacing effect is +11.75 pp; Adaptive is -0.125 pp.

Completion by **total original input+output token quartile**, from
`completion_size_q1` through `completion_size_q4`:

| Replay policy | Q1 (smallest) | Q2 | Q3 | Q4 (largest) |
|---|---:|---:|---:|---:|
| FCFS | 50.75% | 44.00% | 49.75% | 45.50% |
| Adaptive | 52.75% | 45.00% | 50.00% | 44.75% |
| Pacing | 68.50% | 59.25% | 65.50% | 44.25% |

Across resamples the median paired Pacing gains are +17.25, +15.67, +14.75,
and **-1.00 pp** respectively. This supports a smaller-request selection
explanation; the advantage does not extend uniformly to the largest requests.

Every saved run has zero `output_cap_exceeded_count`, and every recorded
truncation matches `reservation_shortfall_count`. These flags describe admitted
executions. The 1,024-token cap does not explain their observed truncations.
The CSVs do not retain output-token delivery totals or admitted input totals.
`token_weighted_served_share` combines consumed input and delivered output;
it cannot identify total delivered output tokens alone. No original-pilot output
total or exact request-level attribution is claimed.

## Actual rule and mechanism

`ironviz_f26/policies.py:Pacing.decide` admits only when reservation R fits both
global remaining money and the currently released spending allowance:

```
spent + R <= B * min(1, elapsed_fraction + 0.05)
R <= global_remaining
```

Settlement is immediate and uses actual capped/reservation-limited execution
cost. The allowance replenishes with time and unspent allowance carries forward.
Large reservations can fail while smaller ones fit. Rejections are terminal:
there is no queue, retry, chronological reordering or future-cost optimization.
Pacing therefore performs **time-dependent cost selection**, in addition to
preserving budget for later arrivals. This can produce count gains even without
a temporal decline in costs. The pilot fixture has no imposed October-like trend.

Training mean reservations limit allowed output even with a generous model cap.
An output above its reservation-funded limit truncates; rejecting fewer requests
therefore creates both more completions and more partial outputs. Mean reservation
is an execution assumption, not merely an admission estimate in strict mode.

## One tiny controlled check

`tools/investigate_pacing.py` uses 50 source requests: ten training, forty
evaluation; six policy runs across caps 16 and 1,024; **240 admission decisions**.
Same fixed seed, request order, prices, roster and budget for both caps. There is
no bootstrap and no routing. Input tiers 100/900 tokens and output lengths
10/20/30/60 are shuffled independently; training mean output is exactly 30.
All six runs share a budget of 9,240 micro-USD. Runtime: **0.222 seconds**.

| Cap | Policy | Complete | Truncated | Rejected | Delivered output tokens | Utilization |
|---|---|---:|---:|---:|---:|---:|
| 16 | FCFS | 6 | 18 | 16 | 348 | 99.00% |
| 16 | Adaptive | 10 | 26 | 4 | 516 | 96.49% |
| 16 | Pacing | 10 | 25 | 5 | 500 | 86.58% |
| 1,024 | FCFS | 24 | 5 | 11 | 640 | 98.92% |
| 1,024 | Adaptive | 26 | 9 | 5 | 790 | 98.38% |
| 1,024 | Pacing | 25 | 10 | 5 | 780 | 89.61% |

The generous cap has no cap-exceeding admissions, but longer outputs still
truncate at the 30-token mean reservation. Pacing's small count gain persists:
25 versus 24, despite less spending. This control explains a possible mechanism;
it does not estimate the cause or magnitude of the original 11.875-pp pilot effect.

At cap 1,024, low-input-tier completion is FCFS 60%, Adaptive 70%, Pacing 73.33%;
high-input-tier completion is FCFS 60%, Adaptive 50%, Pacing 30%. Pacing admits
all 30 low-input requests and five of ten high-input requests, versus FCFS 22
and seven. All five Pacing denials are high-input requests which fit global money
but not current pace credit. For example, request control-13 has reservation 930,
global money 8,880, and pace credit 795: rejection is exactly the intended rule.

An independent formula checked all **80 Pacing decisions**, with **zero
mismatches**. No admission-rule implementation bug was confirmed. This is a
bounded check, not a proof over every possible configuration.

Total output rises from 640 to 780, but output within fully completed requests
falls from 490 to 480; truncated output rises from 150 to 300. Counting completed
requests and counting delivered tokens can favor different interpretations.
Neither measures task utility. Some money remains unused because dropped earlier
requests are not retried; the policy is not a global completion-count optimizer.

## Verdict and scope

The advantage is **mechanically understandable**, consistent with intended
time-dependent reservation filtering, smaller-request selection and strict
training-based output limits. It is not explained by the original pilot's
1,024-token cap, and no Pacing implementation defect was found. Missing pilot
event/output totals prevent exact output-volume or event-level causal decomposition.

These are synthetic-pilot observations, not historical October findings. The
historical results remain pre-correction and have different workloads, prices,
caps/truncation prevalence and allocation settings. No conclusion about October
or institutional policy quality follows from this small control.

New outputs are separate in `outputs/pacing_investigation/`: saved-pilot aggregate
extracts, controlled outcomes/size groups/events/requests, independent rule audit,
metadata and protected-file verification. Original pilot outputs remain unchanged.
