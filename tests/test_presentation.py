"""Saved-table and handoff checks only; no simulation or figure generation."""
import hashlib
import json
from pathlib import Path
import re
import shutil

import numpy as np
import pandas as pd

from tools import build_presentation as export

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'results/presentation'


def test_policy_table_reconciles_all_24_canonical_runs():
    source=pd.read_csv(ROOT/'results/canonical/policies/run_metrics.csv').set_index('run_id')
    chart=pd.read_csv(DATA/'policy_budget_summary.csv').set_index('source_run_id')
    assert len(chart)==24 and chart.index.is_unique
    assert source.index.difference(chart.index).empty
    assert chart.completed_requests.equals(source.loc[chart.index].completed_original.rename('completed_requests'))
    assert (chart.completed_requests+chart.truncated_requests+chart.rejected_requests==chart.request_count).all()
    assert np.allclose(chart.completion_pct+chart.truncation_pct+chart.rejection_pct,100)
    assert np.allclose(chart.spend_usd*1e6,source.loc[chart.index].realized_cost_micro_usd,atol=.0001,rtol=0)
    assert np.allclose(chart.spend_usd+chart.unused_budget_usd,chart.budget_usd)
    assert chart[chart.policy=='FCFS'].completion_difference_pp.eq(0).all()


def test_tenant_tradeoffs_pair_the_same_tenant():
    chart=pd.read_csv(DATA/'tenant_tradeoffs_70pct.csv')
    assert len(chart)==36 and not chart.duplicated(['tenant','policy']).any()
    base=chart[chart.policy=='FCFS'].set_index('tenant')
    for row in chart.itertuples():
        assert row.completed_requests+row.truncated_requests+row.rejected_requests==row.request_count
        assert row.completion_difference_requests==row.completed_requests-base.loc[row.tenant].completed_requests
        assert np.isclose(row.completion_difference_pp,100*row.completion_difference_requests/row.request_count)
    engineering=chart[(chart.tenant=='org-engineering-dev')&(chart.policy=='Adaptive')].iloc[0]
    assert engineering.completion_difference_requests==-1900


def test_bootstrap_probes_keep_method_and_replay_separate():
    chart=pd.read_csv(DATA/'bootstrap_methods_70pct.csv')
    assert len(chart)==24 and not chart.duplicated(['bootstrap_method','replicate','policy']).any()
    for method,folder in [('local_12h','local_bootstrap'),('day_block','day_bootstrap')]:
        raw=pd.read_csv(ROOT/f'results/canonical/{folder}/run_metrics.csv').set_index('run_id')
        selected=chart[chart.bootstrap_method==method]
        assert selected.groupby('replicate').size().to_dict()=={0:6,1:6}
        for row in selected.itertuples():
            assert row.replicate==raw.loc[row.source_run_id].replicate
            assert row.workload_kind==raw.loc[row.source_run_id].workload_kind
            assert row.completed_requests==raw.loc[row.source_run_id].completed_original


def test_october_summary_uses_49_paired_resamples_only():
    rates=pd.read_csv(DATA/'monte_carlo/replicate_results.csv')
    summary=pd.read_csv(DATA/'monte_carlo/paired_effects.csv').set_index('policy')
    raw=pd.read_csv(ROOT/'results/monte_carlo/main_run_metrics.csv').set_index('run_id')
    assert len(rates)==300 and rates.groupby('replicate').size().eq(6).all()
    assert not rates.duplicated(['replicate','policy']).any()
    base=rates[rates.policy=='FCFS'].set_index('replicate')
    for row in rates.itertuples():
        assert np.isclose(row.completion_difference_pp,row.completion_pct-base.loc[row.replicate].completion_pct)
        assert row.completed_requests==raw.loc[row.source_run_id].completed_original
        assert row.completed_requests+row.truncated_requests+row.rejected_requests==row.request_count
    for policy,g in rates[rates.replicate>0].groupby('policy'):
        record=summary.loc[policy];effect=g.completion_difference_pp
        assert record.resamples==49 and record.wins+record.ties+record.losses==49
        assert np.isclose(record.median_difference_pp,effect.median())
        assert np.isclose(record.q25_difference_pp,effect.quantile(.25))
        assert np.isclose(record.p95_difference_pp,effect.quantile(.95))
        assert record.wins==(effect>0).sum()
    assert summary.loc['Pacing'].wins==49
    assert summary.loc['Quotas'].reversals_from_replay==18


def test_reservation_sensitivity_matches_the_same_ten_draws():
    source=pd.read_csv(ROOT/'results/monte_carlo/quantile_run_metrics.csv')
    mean=pd.read_csv(ROOT/'results/monte_carlo/main_run_metrics.csv')
    chart=pd.read_csv(DATA/'monte_carlo/reservation_sensitivity.csv').set_index('policy')
    source=source[source.replicate>0]
    fcfs=source[source.policy=='FCFS'].set_index('replicate')
    for policy,g in source.groupby('policy'):
        effect=100*(g.set_index('replicate').completion_rate_original-fcfs.completion_rate_original)
        matched=mean[(mean.policy==policy)&mean.replicate.between(1,10)]
        assert chart.loc[policy].resamples==10
        assert np.isclose(chart.loc[policy].quantile_reservation_paired_median_pp,effect.median())
        assert np.isclose(chart.loc[policy].mean_reservation_median_completion_pct,100*matched.completion_rate_original.median())


def test_published_study_samples_and_source_fingerprints():
    train=pd.read_csv(ROOT/'results/monte_carlo/training.csv')
    evaluation=pd.read_csv(ROOT/'results/monte_carlo/evaluation.csv')
    assert len(train)==1250 and len(evaluation)==5000
    assert set(train.request_id).isdisjoint(evaluation.request_id)
    assert pd.to_datetime(train.timestamp,utc=True).max()<pd.to_datetime(evaluation.timestamp,utc=True).min()
    assert evaluation.tenant.nunique()==6
    provenance=json.loads((DATA/'provenance.json').read_text())
    for name,expected in provenance['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name


def test_builder_cannot_import_simulation_implementation():
    import ast
    tree=ast.parse((ROOT/'tools/build_presentation.py').read_text(encoding='utf-8'))
    modules=[node.module or '' for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
    modules += [alias.name for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names]
    assert not any(module.startswith(('ironviz_f26','src')) for module in modules)


def test_dictionary_and_landing_links_resolve():
    dictionary=(DATA/'data_dictionary.md').read_text(encoding='utf-8')
    provenance=json.loads((DATA/'provenance.json').read_text())
    assert all('\\' not in path for path in provenance['canonical_sha256'])
    for path in DATA.rglob('*.csv'):
        frame=pd.read_csv(path)
        assert path.stat().st_size<150_000
        assert hashlib.sha256(path.read_bytes()).hexdigest()==provenance['outputs'][path.relative_to(DATA).as_posix()]['sha256']
        for column in frame.columns:
            assert f'| `{column}` |' in dictionary
    for document in [ROOT/'README.md',ROOT/'VISUALIZATION_HANDOFF.md',ROOT/'documentation/MONTE_CARLO.md',ROOT/'documentation/DATA_CONTRACT.md']:
        for link in re.findall(r'\]\(([^)]+)\)',document.read_text(encoding='utf-8')):
            if link.startswith(('https://','http://','#')):
                continue
            assert (document.parent/link.split('#')[0]).exists(),f'{document}: {link}'


def test_regeneration_works_without_raw_or_ignored_experiment_outputs(tmp_path,monkeypatch):
    # Copy only small result inputs, not the repository or an environment.
    shutil.copytree(ROOT/'results/canonical',tmp_path/'results/canonical')
    shutil.copytree(ROOT/'results/monte_carlo',tmp_path/'results/monte_carlo')
    for path in (ROOT/'results').glob('analysis_*.csv'):
        shutil.copyfile(path,tmp_path/'results'/path.name)
    target=tmp_path/'results/presentation';target.mkdir(parents=True)
    monkeypatch.setattr(export,'ROOT',tmp_path);monkeypatch.setattr(export,'DEST',target)
    tables=export.build()
    for name,frame in tables.items():
        expected=pd.read_csv(DATA/name)
        pd.testing.assert_frame_equal(frame.reset_index(drop=True),expected,check_dtype=False,rtol=1e-10,atol=1e-9)
    provenance=json.loads((target/'provenance.json').read_text())
    for name,expected in provenance['canonical_sha256'].items():
        assert hashlib.sha256((tmp_path/name).read_bytes()).hexdigest()==expected
