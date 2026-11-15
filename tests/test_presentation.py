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


def test_pilot_summary_uses_29_paired_resamples_only():
    rates=pd.read_csv(DATA/'monte_carlo_pilot_replicates.csv')
    summary=pd.read_csv(DATA/'monte_carlo_pilot_summary.csv').set_index('policy')
    assert len(rates)==90 and rates.groupby('replicate').size().eq(3).all()
    assert not rates.duplicated(['replicate','policy']).any()
    base=rates[rates.policy=='FCFS'].set_index('replicate')
    for row in rates.itertuples():
        assert np.isclose(row.completion_difference_pp,row.completion_pct-base.loc[row.replicate].completion_pct)
    for policy,g in rates[rates.replicate>0].groupby('policy'):
        record=summary.loc[policy];effect=g.completion_difference_pp
        assert record.resamples==29 and record.wins+record.ties+record.losses==29
        assert np.isclose(record.median_completion_difference_pp,effect.median())
        assert np.isclose(record.q25_completion_difference_pp,effect.quantile(.25))
        assert record.wins==(effect>0).sum()
    assert summary.loc['Adaptive'].strict_ranking_reversals==16
    assert summary.loc['Pacing'].wins==29


def test_dictionary_and_landing_links_resolve():
    dictionary=(DATA/'data_dictionary.md').read_text(encoding='utf-8')
    provenance=json.loads((DATA/'provenance.json').read_text())
    assert all('\\' not in path for path in provenance['canonical_sha256'])
    for path in DATA.glob('*.csv'):
        frame=pd.read_csv(path)
        assert path.stat().st_size<150_000
        assert hashlib.sha256(path.read_bytes()).hexdigest()==provenance['outputs'][path.name]['sha256']
        for column in frame.columns:
            assert f'| `{column}` |' in dictionary
    for document in [ROOT/'README.md',ROOT/'VISUALIZATION_HANDOFF.md',ROOT/'documentation/MONTE_CARLO.md',ROOT/'SCHEMA.md']:
        for link in re.findall(r'\]\(([^)]+)\)',document.read_text(encoding='utf-8')):
            if link.startswith(('https://','http://','#')):
                continue
            assert (document.parent/link.split('#')[0]).exists(),f'{document}: {link}'


def test_regeneration_works_without_ignored_pilot_outputs(tmp_path,monkeypatch):
    # Copy only small result inputs, not the repository or an environment.
    shutil.copytree(ROOT/'results/canonical',tmp_path/'results/canonical')
    target=tmp_path/'results/presentation';target.mkdir(parents=True)
    for name in ('monte_carlo_pilot_replicates.csv','provenance.json'):
        shutil.copyfile(DATA/name,target/name)
    monkeypatch.setattr(export,'ROOT',tmp_path);monkeypatch.setattr(export,'DEST',target)
    tables=export.build()
    for name,frame in tables.items():
        expected=pd.read_csv(DATA/name)
        pd.testing.assert_frame_equal(frame.reset_index(drop=True),expected,check_dtype=False,rtol=1e-10,atol=1e-9)
    provenance=json.loads((target/'provenance.json').read_text())
    for name,expected in provenance['canonical_sha256'].items():
        assert hashlib.sha256((tmp_path/name).read_bytes()).hexdigest()==expected
