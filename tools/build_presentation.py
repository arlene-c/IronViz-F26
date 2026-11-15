"""Build small presentation tables from saved CSVs only. No simulator imports."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'results/presentation'

PURPOSES = {
    'policy_budget_summary.csv': 'All six policies at four modeled budgets in the historical October evaluation replay.',
    'tenant_tradeoffs_70pct.csv': 'Each of six historical operational tenants under six policies at 70% budget.',
    'bootstrap_methods_70pct.csv': 'Two historical sampling-method probes, each with the same replay and one distinct resample at 70%.',
    'monte_carlo_pilot_summary.csv': 'Three policy summaries computed from 29 fictional local-block resamples, excluding replay.',
    'monte_carlo_pilot_replicates.csv': 'Every policy/replicate from the fictional pilot: three policies, replay plus 29 resamples.',
}

DESCRIPTIONS = {
    'dataset': ('label', 'Historical October replay/probe or fictional synthetic pilot; never pool these populations.'),
    'result_status': ('label', 'historical_pre_correction_provisional or exploratory_synthetic.'),
    'policy': ('label', 'FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold.'),
    'budget_pct': ('percent', 'Modeled budget as a percentage of original-model reference expenditure for that workload.'),
    'source_run_id': ('identifier', 'Original saved run identifier; scope with dataset and bootstrap_method when present.'),
    'request_count': ('requests', 'Demand denominator: evaluation requests, or tenant evaluation requests in the tenant table.'),
    'completed_requests': ('requests', 'Fully completed original requests; excludes truncations and counterfactual routing.'),
    'completion_pct': ('percent', '100 times completed_requests/request_count.'),
    'truncated_requests': ('requests', 'Admitted executions that did not finish their original observed output.'),
    'truncation_pct': ('percent', '100 times truncated_requests/request_count.'),
    'rejected_requests': ('requests', 'Requests denied execution; disjoint from completed and truncated.'),
    'rejection_pct': ('percent', '100 times rejected_requests/request_count.'),
    'admitted_requests': ('requests', 'Completed plus truncated executions; not fully served requests.'),
    'budget_usd': ('modeled USD', 'Global budget converted from integer micro-USD; not an actual bill.'),
    'spend_usd': ('modeled USD', 'Realized execution expenditure, including truncated executions.'),
    'unused_budget_usd': ('modeled USD', 'Global budget minus execution expenditure; not unused reservations.'),
    'budget_utilization_pct': ('percent', '100 times expenditure/global budget.'),
    'fcfs_completed_requests': ('requests', 'Completed requests for the matching FCFS workload, budget and replicate; tenant-specific in tenant table.'),
    'fcfs_completion_pct': ('percent', 'Completion percentage for the matching FCFS baseline.'),
    'completion_difference_requests': ('requests', 'Policy completed count minus matching FCFS completed count.'),
    'completion_difference_pp': ('percentage points', 'Policy completion percentage minus matching FCFS percentage; not relative percent change.'),
    'spend_difference_usd': ('modeled USD', 'Policy spend minus matching FCFS spend; negative means lower expenditure.'),
    'utilization_difference_pp': ('percentage points', 'Policy budget utilization minus matching FCFS utilization.'),
    'min_tenant_completion_pct': ('percent', 'Lowest completion percentage among operational tenants; not demographic fairness.'),
    'tenant_completion_gap_pp': ('percentage points', 'Highest tenant completion rate minus lowest tenant completion rate.'),
    'tenant': ('identifier', 'Operational billing/project group, not an individual or demographic group.'),
    'bootstrap_method': ('label', 'local_12h: 12-hour blocks within +/-3 days; day_block: whole-day resampling.'),
    'replicate': ('integer', '0 is original replay; positive values identify resampled workloads.'),
    'workload_kind': ('label', 'replay, local_12h_block_bootstrap or day_block_bootstrap; keep replay separate.'),
    'resamples': ('workloads', 'Number of positive-replicate paired observations; excludes replay.'),
    'median_completion_difference_pp': ('percentage points', 'Median paired completion-rate difference against FCFS across resamples.'),
    'q25_completion_difference_pp': ('percentage points', '25th percentile of paired resample differences.'),
    'q75_completion_difference_pp': ('percentage points', '75th percentile of paired resample differences.'),
    'min_completion_difference_pp': ('percentage points', 'Minimum observed paired resample difference.'),
    'max_completion_difference_pp': ('percentage points', 'Maximum observed paired resample difference.'),
    'p025_completion_difference_pp': ('percentage points', '2.5th percentile of paired resample outcomes; descriptive, not a confidence bound.'),
    'p975_completion_difference_pp': ('percentage points', '97.5th percentile of paired resample outcomes; descriptive, not a confidence bound.'),
    'wins': ('workloads', 'Resamples where policy completion rate exceeds FCFS.'),
    'ties': ('workloads', 'Resamples with equal policy and FCFS completion rates; all FCFS rows tie themselves.'),
    'losses': ('workloads', 'Resamples where policy completion rate is below FCFS.'),
    'win_pct': ('percent', '100 times wins/resamples; conditional frequency, not real-world success probability.'),
    'replay_completion_pct': ('percent', 'Policy completion percentage in the separate original replay.'),
    'replay_completion_difference_pp': ('percentage points', 'Policy-minus-FCFS completion difference in replay, excluded from resample statistics.'),
    'median_completion_pct': ('percent', 'Median policy completion percentage across resamples.'),
    'median_min_tenant_completion_pct': ('percent', 'Median of each resample\'s minimum tenant completion percentage.'),
    'median_budget_utilization_pct': ('percent', 'Median policy budget utilization across resamples.'),
    'strict_ranking_reversals': ('workloads', 'Resamples with a strict sign opposite the replay policy-minus-FCFS effect; ties are excluded, null if replay tied.'),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_table(runs, dataset):
    key=['scenario_id','budget_fraction','replicate']
    baseline=runs[runs.policy=='FCFS'][key+['completed_original','realized_cost_micro_usd','budget_utilization']].rename(
        columns={'completed_original':'fcfs_count','realized_cost_micro_usd':'fcfs_spend','budget_utilization':'fcfs_util'})
    data=runs.merge(baseline,on=key,validate='many_to_one')
    assert data.fcfs_count.notna().all()
    result=pd.DataFrame(dict(dataset=dataset,result_status='historical_pre_correction_provisional',
        policy=data.policy,budget_pct=(100*data.budget_fraction).round().astype(int),source_run_id=data.run_id,
        request_count=data.request_count,completed_requests=data.completed_original,
        completion_pct=100*data.completed_original/data.request_count,truncated_requests=data.truncated,
        truncation_pct=100*data.truncated/data.request_count,rejected_requests=data.rejected,
        rejection_pct=100*data.rejected/data.request_count,admitted_requests=data.admitted,
        budget_usd=data.budget_micro_usd/1e6,spend_usd=data.realized_cost_micro_usd/1e6,
        unused_budget_usd=data.budget_remaining_micro_usd/1e6,budget_utilization_pct=100*data.budget_utilization,
        fcfs_completed_requests=data.fcfs_count,fcfs_completion_pct=100*data.fcfs_count/data.request_count,
        completion_difference_requests=data.completed_original-data.fcfs_count,
        completion_difference_pp=100*(data.completed_original-data.fcfs_count)/data.request_count,
        spend_difference_usd=(data.realized_cost_micro_usd-data.fcfs_spend)/1e6,
        utilization_difference_pp=100*(data.budget_utilization-data.fcfs_util),
        min_tenant_completion_pct=100*data.min_tenant_completion_rate,
        tenant_completion_gap_pp=100*data.max_min_completion_gap))
    return result


def tenant_table(tenants):
    data=tenants[tenants.budget_fraction==.7].copy()
    baseline=data[data.policy=='FCFS'][['tenant','completed_original','realized_cost_micro_usd']].rename(
        columns={'completed_original':'fcfs_count','realized_cost_micro_usd':'fcfs_spend'})
    data=data.merge(baseline,on='tenant',validate='many_to_one')
    return pd.DataFrame(dict(dataset='historical_october_replay',result_status='historical_pre_correction_provisional',
        tenant=data.tenant,policy=data.policy,budget_pct=70,source_run_id=data.run_id,request_count=data.demand_requests,
        completed_requests=data.completed_original,completion_pct=100*data.completed_original/data.demand_requests,
        fcfs_completed_requests=data.fcfs_count,fcfs_completion_pct=100*data.fcfs_count/data.demand_requests,
        completion_difference_requests=data.completed_original-data.fcfs_count,
        completion_difference_pp=100*(data.completed_original-data.fcfs_count)/data.demand_requests,
        rejected_requests=data.rejected,truncated_requests=data.truncated,
        spend_usd=data.realized_cost_micro_usd/1e6,spend_difference_usd=(data.realized_cost_micro_usd-data.fcfs_spend)/1e6))


def pilot_tables(raw=None, published=None):
    if raw is not None:
        rates=pd.DataFrame(dict(dataset='fictional_monte_carlo_pilot',result_status='exploratory_synthetic',
            policy=raw.policy,source_run_id=raw.run_id,bootstrap_method='local_12h',budget_pct=70,
            replicate=raw.replicate,workload_kind=raw.workload_kind,request_count=raw.request_count,
            completed_requests=raw.completed_original,completion_pct=100*raw.completion_rate_original,
            rejected_requests=raw.rejected,rejection_pct=100*raw.rejected/raw.request_count,
            truncated_requests=raw.truncated,truncation_pct=100*raw.truncated/raw.request_count,
            fcfs_completion_pct=100*raw.fcfs_completion_rate,
            completion_difference_pp=raw.paired_completion_rate_difference_pp,
            min_tenant_completion_pct=100*raw.min_tenant_completion_rate,budget_utilization_pct=100*raw.budget_utilization))
    else:
        rates=published.copy()
    assert len(rates)==90 and rates.groupby('replicate').size().eq(3).all()
    assert not rates.duplicated(['replicate','policy']).any()
    records=[]
    for policy,group in rates[rates.replicate>0].groupby('policy'):
        effect=group.completion_difference_pp
        replay=rates[(rates.policy==policy)&(rates.replicate==0)].iloc[0]
        sign=np.sign(replay.completion_difference_pp)
        records.append(dict(dataset='fictional_monte_carlo_pilot',result_status='exploratory_synthetic',
            policy=policy,bootstrap_method='local_12h',budget_pct=70,resamples=len(group),
            median_completion_difference_pp=effect.median(),q25_completion_difference_pp=effect.quantile(.25),
            q75_completion_difference_pp=effect.quantile(.75),min_completion_difference_pp=effect.min(),
            max_completion_difference_pp=effect.max(),p025_completion_difference_pp=effect.quantile(.025),
            p975_completion_difference_pp=effect.quantile(.975),wins=int((effect>0).sum()),ties=int((effect==0).sum()),
            losses=int((effect<0).sum()),win_pct=100*(effect>0).mean(),
            replay_completion_pct=replay.completion_pct,replay_completion_difference_pp=replay.completion_difference_pp,
            median_completion_pct=group.completion_pct.median(),median_min_tenant_completion_pct=group.min_tenant_completion_pct.median(),
            median_budget_utilization_pct=group.budget_utilization_pct.median(),
            strict_ranking_reversals=int((np.sign(effect)*sign<0).sum()) if sign else None))
    return rates,pd.DataFrame(records)


def build():
    canonical=ROOT/'results/canonical'
    protected={str(p.relative_to(ROOT)):digest(p) for p in canonical.rglob('*') if p.is_file()}
    snapshots={}
    def read(relative):
        path=ROOT/relative; snapshots[relative]=digest(path)
        return pd.read_csv(path)
    policies=historical_table(read('results/canonical/policies/run_metrics.csv'),'historical_october_replay')
    tenants=tenant_table(read('results/canonical/policies/tenant_metrics.csv'))
    probes=[]
    for folder,method in [('local_bootstrap','local_12h'),('day_bootstrap','day_block')]:
        raw=read(f'results/canonical/{folder}/run_metrics.csv')
        table=historical_table(raw,'historical_bootstrap_probe')
        table['bootstrap_method']=method;table['replicate']=raw.replicate.to_numpy();table['workload_kind']=raw.workload_kind.to_numpy()
        probes.append(table)
    pilot_path=ROOT/'outputs/monte_carlo_pilot/policy_completion_rates.csv'
    if pilot_path.exists():
        rates,summary=pilot_tables(raw=read('outputs/monte_carlo_pilot/policy_completion_rates.csv'))
    else:
        # The published replicate table is sufficient to rebuild the pilot summary
        # from a fresh checkout; running policies is never a fallback.
        rates,summary=pilot_tables(published=read('results/presentation/monte_carlo_pilot_replicates.csv'))
    tables={'policy_budget_summary.csv':policies,'tenant_tradeoffs_70pct.csv':tenants,
        'bootstrap_methods_70pct.csv':pd.concat(probes,ignore_index=True),
        'monte_carlo_pilot_summary.csv':summary,'monte_carlo_pilot_replicates.csv':rates}
    assert len(policies)==24 and len(tenants)==36 and len(tables['bootstrap_methods_70pct.csv'])==24
    for frame in [policies,*probes]:
        assert (frame.completed_requests+frame.truncated_requests+frame.rejected_requests==frame.request_count).all()
        assert np.allclose(frame.spend_usd+frame.unused_budget_usd,frame.budget_usd)
    DEST.mkdir(parents=True,exist_ok=True)
    dictionary=['# Presentation data dictionary','',
        'Chart-ready saved results only. Historical tables are pre-correction and provisional; the fictional pilot is exploratory.',
        'All `_pct` columns are already 0-100 percentages; `_pp` columns are percentage-point differences. USD columns are modeled costs.',
        'No routing is present. Admitted requests can truncate. No percentile field is an inferential confidence interval.','',
        'Historical policy key: `(policy, budget_pct)`; tenant key: `(tenant, policy)`; bootstrap key: `(bootstrap_method, replicate, policy)`;',
        'pilot key: `(replicate, policy)`. Join pilot summary to replicates on policy only after selecting the intended replicate population.',
        'Each historical bootstrap method contains the SAME replay plus ONE resample; do not count the duplicate replays as independent evidence.',
        'Pilot summary uses only the 29 resamples; pilot replicates also includes replay 0. FCFS differences are zero by construction.','']
    for name,frame in tables.items():
        for column in frame.columns:
            assert column in DESCRIPTIONS,f'Undocumented column: {column}'
        frame.to_csv(DEST/name,index=False,float_format='%.12g',lineterminator='\n')
        dictionary.extend([f'## {name}', '', PURPOSES[name], '', f'{len(frame)} rows. Saved source paths and SHA-256 hashes are in [provenance.json](provenance.json).', '',
            '| Column | Unit | Definition |','|---|---|---|'])
        dictionary.extend(f'| `{column}` | {DESCRIPTIONS[column][0]} | {DESCRIPTIONS[column][1]} |' for column in frame.columns)
        dictionary.append('')
    (DEST/'data_dictionary.md').write_text('\n'.join(dictionary).rstrip()+'\n',encoding='utf-8')
    for relative,expected in {**protected,**snapshots}.items():
        # The fallback input is itself the regenerated presentation table; its
        # normalized decimal representation is checked by tests, not a source archive.
        if not relative.startswith('results/presentation/'):
            assert digest(ROOT/relative)==expected,relative
    provenance=dict(generator='tools/build_presentation.py; pandas aggregations only, no policy execution',
        historical_status='pre-correction provisional; original canonical files unchanged',pilot_status='exploratory synthetic; 29 resamples plus replay',
        source_sha256=snapshots,canonical_sha256=protected,
        outputs={name:dict(rows=len(frame),columns=list(frame.columns),sha256=digest(DEST/name)) for name,frame in tables.items()})
    # Pilot provenance remains available even when regenerating from the published table.
    metadata=ROOT/'outputs/monte_carlo_pilot/scenario_metadata.json'
    if metadata.exists():
        source=json.loads(metadata.read_text())
        provenance['pilot_configuration']={k:source[k] for k in ('seed','training_request_count','evaluation_request_count','config','pilot_runtime_seconds','retimed_fixture','synthetic_price_scaling')}
        provenance['source_sha256']['outputs/monte_carlo_pilot/scenario_metadata.json']=digest(metadata)
    elif (DEST/'provenance.json').exists():
        previous=json.loads((DEST/'provenance.json').read_text())
        provenance['pilot_configuration']=previous['pilot_configuration']
        provenance['pilot_archived_source_sha256']=previous.get('pilot_archived_source_sha256',
            {k:v for k,v in previous['source_sha256'].items() if k.startswith('outputs/monte_carlo_pilot/')})
    (DEST/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    print('Built '+', '.join(f'{name}: {len(frame)} rows' for name,frame in tables.items()))
    return tables


if __name__=='__main__':
    build()
