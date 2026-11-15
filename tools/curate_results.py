"""Export completed aggregates only; never import or execute the simulator."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import pandas as pd

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    root = Path(__file__).resolve().parents[1]
    destination = root / 'results/canonical'
    entries = []
    groups = {
        'policies': ('authoritative_policies', ['run_metrics.csv', 'tenant_metrics.csv', 'experiment_summary.csv', 'policy_comparisons.csv', 'regime_map.csv', 'scenario_metadata.json', 'findings.md']),
        'local_bootstrap': ('authoritative_local_bootstrap', ['run_metrics.csv', 'tenant_metrics.csv', 'policy_comparisons.csv', 'scenario_metadata.json']),
        'day_bootstrap': ('authoritative_day_bootstrap', ['run_metrics.csv', 'tenant_metrics.csv', 'policy_comparisons.csv', 'scenario_metadata.json']),
        'configuration': ('canonical_reference', ['price_catalog_micro_usd.json', 'routing_compatibility.json', 'price_sources.csv', 'adaptation_report.json']),
    }
    for label, (source_name, files) in groups.items():
        source = root / 'outputs' / source_name
        if label != 'configuration':
            metadata = json.loads((source / 'scenario_metadata.json').read_text())
            runs = pd.read_csv(source / 'run_metrics.csv')
            expected = len(metadata['scenarios']) * len(metadata['config']['budget_fractions']) * len(metadata['config']['policies'])
            if len(runs) != expected or runs.run_id.duplicated().any():
                raise ValueError(f'Incomplete or duplicate runs: {source}')
            if not ((runs.completed_original + runs.completed_routed + runs.truncated + runs.rejected) == runs.request_count).all():
                raise ValueError(f'Outcome reconciliation failed: {source}')
            if not (runs.realized_cost_micro_usd + runs.budget_remaining_micro_usd == runs.budget_micro_usd).all():
                raise ValueError(f'Budget reconciliation failed: {source}')
        target = destination / label
        target.mkdir(parents=True, exist_ok=True)
        for name in files:
            original, copied = source / name, target / name
            before = digest(original)
            shutil.copyfile(original, copied)
            if digest(original) != before or digest(copied) != before:
                raise ValueError(f'Source changed during copy: {original}')
            entries.append(dict(path=copied.relative_to(root).as_posix(), source=original.relative_to(root).as_posix(), sha256=before, bytes=copied.stat().st_size, export='byte-identical'))
    source = root / 'outputs/authoritative_policies/budget_timeseries.parquet'
    before = digest(source)
    frame = pd.read_parquet(source)
    selected = [pd.concat([g.iloc[::10], g.tail(1)]).drop_duplicates(['run_id', 'request_id']) for _, g in frame.groupby('run_id', sort=False)]
    columns = ['run_id', 'scenario_id', 'policy', 'budget_fraction', 'replicate', 'workload_kind', 'timestamp', 'global_remaining_micro_usd', 'cumulative_spend_micro_usd']
    target = destination / 'policies/budget_trajectories.csv'
    pd.concat(selected)[columns].to_csv(target, index=False)
    if digest(source) != before:
        raise ValueError('Timeseries changed during export')
    entries.append(dict(path=target.relative_to(root).as_posix(), source=source.relative_to(root).as_posix(), source_sha256=before, sha256=digest(target), bytes=target.stat().st_size, export='every tenth existing sampled row per run plus final row; approximately every 1000 original events; no request IDs'))
    manifest = dict(status='PRE-CORRECTION; provisional research results', source_checkout=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(), generating_revision='not embedded by original experiments; source_checkout identifies curation only', warning='Original outputs unchanged; repaired code does not validate old results. Bootstrap sets each contain replay plus ONE resample; no supported confidence intervals.', files=entries)
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Curated {len(entries)} files; {sum(e["bytes"] for e in entries):,} bytes; no simulations executed')

if __name__ == '__main__':
    main()
