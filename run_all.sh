#!/usr/bin/env bash
# Reproduce every result and figure from the two raw competition files.
set -euo pipefail
cd "$(dirname "$0")"
python src/ironviz_experiments.py \
  --openai data/raw/openai_pipeline_telemetry_raw.csv \
  --gemini data/raw/gemini_pipeline_telemetry_raw.csv \
  --prices config/prices.csv --out results
python charts/make_static.py results/clean_requests.csv results/results.csv results/trace.csv figures/static
python charts/make_animated.py results/clean_requests.csv results/results.csv results/trace.csv \
  charts/anim_template.html figures/animated/animated_charts.html
echo "Done. Results in results/, figures in figures/."
