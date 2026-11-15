"""Small regression checks only; never load raw data or execute full-data jobs."""
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_curated_results_are_unchanged_and_reconcile():
    manifest = json.loads((ROOT / 'results/canonical/manifest.json').read_text())
    assert manifest['status'].startswith('PRE-CORRECTION')
    for entry in manifest['files']:
        path = ROOT / entry['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        assert path.stat().st_size < 2_000_000
    runs = pd.read_csv(ROOT / 'results/canonical/policies/run_metrics.csv')
    tenants = pd.read_csv(ROOT / 'results/canonical/policies/tenant_metrics.csv')
    assert len(runs) == 24 and len(tenants) == 144
    assert runs.run_id.is_unique
    assert (runs.completed_original + runs.rejected + runs.truncated == runs.request_count).all()
    assert (runs.realized_cost_micro_usd + runs.budget_remaining_micro_usd == runs.budget_micro_usd).all()
    assert tenants.groupby('run_id').completed_original.sum().sort_index().equals(
        runs.set_index('run_id').completed_original.sort_index())
    expected = dict(FCFS=42573, Quotas=36641, TrainingQuotas=44699, Adaptive=45768, Pacing=46217, Threshold=47384)
    assert runs[runs.budget_fraction == .7].set_index('policy').completed_original.to_dict() == expected
