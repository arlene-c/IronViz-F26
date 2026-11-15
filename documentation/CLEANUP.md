# Repository cleanup manifest

Base: `0e4738824c0cd665b11779849ce274ac9f90112d` (latest team merge). The earlier October study was already committed before this cleanup branch. Git history is the recovery mechanism for removed development artifacts. No archive dump or downloadable package was created.

## Stage A: inspected classification

| Classification | Decision |
|---|---|
| Essential/current | Keep the current backend and its tests; raw-data instructions; price catalog; frozen canonical evidence; current story/dashboard and their templates; descriptive source tables and five static panels. |
| Useful/misplaced | Consolidate the completed October report into MONTE_CARLO.md, its table aggregation into build_presentation.py, and all chart-ready data/dictionary/provenance into results/presentation/. Publish minimal saved run evidence and exact samples so a fresh checkout can verify it. |
| Historically meaningful/superseded | Archive only the original hypotheses/specification and unique Pacing control report. Preserve the legacy algorithm inside the active preparation source for semantic provenance, behind explicit opt-in. |
| Redundant/recoverable | Delete obsolete alternative runners, duplicate contract/dependencies/reports, old fictional-pilot presentation exports and legacy animation. |
| Generated/obsolete | Remove unused legacy experiment tables, duplicate chart CSVs and misleading admission/learning graphics; stop tracking two large reproducible intermediate CSVs while retaining local bytes. |
| Ambiguous/active | Keep cleaned telemetry because the newly merged story actually reads it. Preserve the latest incoming story/dashboard HTML/templates and established descriptive input paths; consolidate its unique accessibility text. Leave all ignored raw/experiment directories untouched. |

Inspection covered tracked sizes, contents, Python imports/APIs, script entry points, source writers/readers, Markdown/configuration references and chart captions. The working inventory and SHA-256 baseline are local under outputs/finalization_audit/. Every action below was checked against retained consumers; affected links/tests/entry points were updated. Source provenance is retained even where no final chart uses the old experiment.

## Stage B: action ledger

| Original path | Action | Reason | Evidence / preserved location |
|---|---|---|---|
| `documentation/SPEC.md` | Archive | Original hypotheses and design decisions have methodological value; superseded as an implementation guide. | documentation/archive/SPEC.md; byte-identical move |
| `documentation/PACING_INVESTIGATION.md` | Archive | Unique controlled mechanism check; historical experiment, not the current study. | documentation/archive/PACING_INVESTIGATION.md; byte-identical move |
| `results/presentation/monte_carlo/README.md` | Consolidate | Consolidate the completed October study into documentation/MONTE_CARLO.md. | documentation/MONTE_CARLO.md; complete report consolidated and updated, not duplicated. |
| `SCHEMA.md` | Delete | Redirect-only duplicate contract. | documentation/DATA_CONTRACT.md is the complete authoritative contract; update test links. |
| `documentation/VALIDATION.md` | Delete | Superseded validation status and fictional-pilot report. | Current fixes consolidated in METHODOLOGY.md; unit tests retain coverage; unique pacing evidence archived. |
| `documentation/archive/INTEGRATION_AUDIT.md` | Delete | Overlapping integration status, superseded by corrected study. | Rounding and semantic findings consolidated in METHODOLOGY.md; canonical adaptation_report.json preserves reconciliation. |
| `documentation/archive/RECONCILIATION_REPORT.md` | Delete | Incomplete report still describes a pending replay. | No final divergence evidence; exact rounding reconciliation retained in canonical configuration and METHODOLOGY.md. |
| `tools/benchmark_fcfs.py` | Delete | Unused development benchmark with a 200K default and evaluation/training overlap. | No code imports or active workflow calls; current CLI and bounded October runner provide retained execution paths. |
| `tools/run_online_fcfs.py` | Delete | Unused alternative full-data estimator experiment. | Zero-prior online semantics are outside final study; no callers; strict current runner retained. |
| `tools/reconcile_reference.py` | Delete | Obsolete full-data compatibility replay entry point. | No callers; published rounding provenance retained in reference_adapter.py and canonical configuration. |
| `tools/curate_results.py` | Delete | One-time curation script can overwrite frozen canonical evidence. | Manifest and exact curated files retained; presentation builder reads them without recuration. |
| `tools/run_monte_carlo_pilot.py` | Delete | Fictional pilot runner superseded by completed October study. | Pairing/block regression tests retained; old experiment recoverable from base Git revision and untouched ignored outputs. |
| `tools/summarize_october_monte_carlo.py` | Delete | Duplicate presentation aggregation entry point. | Its CSV aggregation is consolidated into tools/build_presentation.py; no simulation rerun. |
| `run_all.sh` | Delete | Obsolete all-in-one expensive orchestration. | CLI preparation and optional legacy reproduction documented separately; current chart builders use saved data. |
| `charts/make_animated.py` | Delete | Generated legacy animation superseded by active story/dashboard. | New charts/make_story.py and make_dashboard.py cover current interactive narrative; no retained callers. |
| `charts/anim_template.html` | Delete | Template used only by removed legacy animation builder. | Active story/dashboard templates retained; no external assets depend on it. |
| `figures/animated/animated_charts.html` | Delete | Obsolete rendered legacy admission/routing narrative. | Active story.html/dashboard.html use the six-policy canonical evidence; routing quality was not evaluated. |
| `results/presentation/monte_carlo_pilot_replicates.csv` | Delete | Superseded fictional fixture export, not October evidence. | Original local outputs untouched; committed base revision preserves all 90 records; current 300-run study retained. |
| `results/presentation/monte_carlo_pilot_summary.csv` | Delete | Derived summary of superseded fixture export. | Recoverable from its replicate table in base Git history; current study replaces it in final narrative. |
| `results/expected_output.csv` | Delete | Unused legacy estimator summary, not the current training estimates. | Source pipeline computes it; no retained consumer; current study metadata/sample retains actual training evidence. |
| `results/checks.txt` | Delete | Development assertion log for legacy soft-budget algorithm. | Source assertions and current tests retained; not evidence of strict-budget correctness. |
| `results/exp2_buckets.csv` | Delete | Unused legacy admission-size experiment. | Current corrected study retains full-completion quartiles; old result recoverable in Git. |
| `results/exp3_summary.csv` | Delete | Redundant legacy summary of bootstrap admissions. | Not used by active story/dashboard; corrected paired distributions retained; recoverable in Git. |
| `results/exp4_shock.csv` | Delete | Unreferenced legacy shock experiment outside final study. | No chart/document consumer after consolidation; implementation retained for historical reproduction. |
| `results/results.csv` | Delete | Legacy four-policy admission output superseded in all current charts. | Story/dashboard use canonical six-policy runs; static script narrowed to descriptive panels; Git preserves old routing evidence. |
| `results/trace.csv` | Delete | Legacy four-policy budget traces, no retained chart consumer. | Canonical budget_trajectories.csv supports current story/dashboard; old traces recoverable from Git. |
| `figures/static/04_fingerprints_data.csv` | Delete | Rounded chart intermediate, no reader. | Retained clean input and analysis_team_summary.csv preserve source measurements and denominators. |
| `figures/static/11_weekly_trend_data.csv` | Delete | Rounded duplicate weekly cache/model series. | analysis_weekly_trend.csv contains the retained source series; presentation export makes it chart-ready. |
| `figures/static/ALT_TEXT.txt` | Consolidate | Duplicate static accessibility text; latest remote docs/ALT_TEXT.txt adds unique interactive descriptions. | docs/ALT_TEXT.txt retains descriptions of all five kept static panels plus the newly added dashboard; obsolete 06-11 sections removed. |
| `figures/static/06_cost_vs_access_2D.png` | Delete | Legacy admission/routing chart conflicts with current full-completion narrative. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `figures/static/06_cost_vs_access_2D.svg` | Delete | Legacy admission/routing chart conflicts with current full-completion narrative. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `figures/static/07_team_access_dotplot_1D.png` | Delete | Legacy admission/routing chart conflicts with current full-completion narrative. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `figures/static/07_team_access_dotplot_1D.svg` | Delete | Legacy admission/routing chart conflicts with current full-completion narrative. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `figures/static/08_quantile_dotplot_1D.png` | Delete | Legacy admission/routing chart conflicts with current full-completion narrative. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `figures/static/08_quantile_dotplot_1D.svg` | Delete | Legacy admission/routing chart conflicts with current full-completion narrative. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `figures/static/09_budget_drain_2D.png` | Delete | Legacy admission/routing chart conflicts with current full-completion narrative. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `figures/static/09_budget_drain_2D.svg` | Delete | Legacy admission/routing chart conflicts with current full-completion narrative. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `figures/static/10_policy_heatmap_2D.png` | Delete | Legacy admission/routing chart conflicts with current full-completion narrative. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `figures/static/10_policy_heatmap_2D.svg` | Delete | Legacy admission/routing chart conflicts with current full-completion narrative. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `figures/static/11_weekly_learning_trend_2D.png` | Delete | Title makes an unsupported learning inference from descriptive trends. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `figures/static/11_weekly_learning_trend_2D.svg` | Delete | Title makes an unsupported learning inference from descriptive trends. | Inspected chart source/captions; no HTML image references; current canonical story/dashboard and weekly presentation data preserve the relevant narrative. |
| `results/requests_sim.csv` | Stop tracking; keep local | Reproducible generated intermediate, not published aggregate evidence. | Source preparation can regenerate; existing bytes retained locally and ignored; tests construct tiny fixtures. |
| `results/excluded_rows.csv` | Stop tracking; keep local | Reproducible generated intermediate, not published aggregate evidence. | Source preparation can regenerate; existing bytes retained locally and ignored; tests construct tiny fixtures. |
| `results/presentation/monte_carlo/provenance.json` | Delete | Duplicate presentation manifest. | Exact study plan preserved under results/monte_carlo; one root presentation provenance hashes all saved inputs and CSVs. |
| `tools/investigate_pacing.py` | Delete | One-off development experiment requires the superseded ignored fictional pilot. | Unique measured mechanism result retained in documentation/archive/PACING_INVESTIGATION.md; code and pilot recoverable from base Git revision. |
| `requirements.txt` | Delete | Duplicate dependency list diverged from the installable project. | pyproject.toml is authoritative; optional legacy numba accelerator retained as the legacy extra. |

## Consolidation and preservation

- Canonical values, configuration, manifest and source hashes are unchanged. The original 24 policy runs remain intact.
- The current simulation backend algorithms are unchanged. Only its package description was refreshed. Regression coverage is retained; saved-result tests now check the substantive October study instead of the superseded fixture exports.
- Existing raw telemetry, ignored experiment directories, local virtual environments and personal files were not deleted. The untracked simulation/exclusion CSVs retain their original bytes. Git history still contains old large files; this cleanup reduces the checkout without rewriting history.
- The 25.9 MB clean_requests.csv is intentionally retained as an active visualization input. Descriptive source CSVs remain at their established paths for the newly merged team builders; the single handoff folder contains labeled chart-ready exports generated from them.
- results/monte_carlo/ holds saved primary/Q90 aggregates, metadata, cap/sampling audits, runtime evidence and the exact 1,250/5,000 training/evaluation samples. These are synthetic records, not real institutional telemetry. Original ignored study files remain unchanged.
- One dictionary/provenance pair covers all presentation CSVs. No simulation is a fallback for missing data. Archived Pacing text remains explicitly historical and may mention deleted development entry points; those references document the original experiment rather than current commands.
- src/ironviz_experiments.py retains unique data parsing/descriptive analysis and historical algorithm semantics. Its default now stops before any policy experiment; --run-legacy-experiments is required for old workloads. charts/make_static.py now renders only descriptive panels and uses clean_requests.csv plus an output directory.

## Verification

75 safe tests passed; three scenario sweeps were excluded. All 14 presentation CSVs reconcile with saved sources, including unchanged prior October-study values after explicit count-column renaming. A temporary checkout-layout test rebuilds every table without raw or ignored experiment files. All current local Markdown links resolve. All retained Python files parse. The 24-request CLI fixture validates and runs one FCFS replay (20 evaluation requests). Both interactive builders render to temporary outputs; published HTML/templates match the newer remote visualization revision 162622c. Explicit UTF-8 I/O fixes their confirmed Windows decoding failures. Static rendering also fixes the unsupported Windows %-d date formatter and supplies a portable font fallback; five panels rendered only to a temporary directory. The adapter script now resolves its package import when run directly from the checkout. pip check reports no broken dependencies. Canonical, cleaned/raw source bytes, saved original study artifacts and the two preserved local intermediates match their baselines. No historical sweep, October Monte Carlo run, Q90 run, original pilot, full-data bootstrap or routing factorial is part of this cleanup.

The remote advanced during the audit. The six updated visualization files and unique accessibility descriptions from `162622cf6725f356a5b6f903de9a19541dad3178` were incorporated as file changes without merging or changing main. Both current HTML builders successfully render the corrected Monte Carlo panels against the consolidated exports. The original local base reference remains unchanged.

Source CSV hashes are portable across Windows/Linux: historical descriptive tables use their existing Git LF representation, and saved canonical/Monte Carlo files retain exact bytes via .gitattributes. Numeric descriptive values are unchanged.

Fixed study samples share the saved-evidence folder instead of introducing a nested data directory. The cleanup adds one evidence directory and removes the obsolete animation directory; documentation is reduced overall.

Final staged review: 145 tracked files become 127, and checkout content drops from 63.44 MB to approximately 31.86 MB (49.8% smaller; Git history unchanged). All 59 staged input/output fingerprints match the presentation provenance, all 57 current local document links resolve, and no raw telemetry, local experiment output, environment or cache is staged.
