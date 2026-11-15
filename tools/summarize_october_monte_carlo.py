"""Summarize the completed bounded October study. CSV aggregation only."""
import hashlib
from itertools import combinations
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ironviz_f26.experiments import _seed_value
SOURCE=ROOT/'outputs/monte_carlo_october'
DEST=ROOT/'results/presentation/monte_carlo'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def block_draw_audit():
    """Check RNG block choices independently of replicate-specific request IDs.

    Reconstruct only 48 integer choices per replicate; never rerun policies or
    materialize bootstrap request workloads.
    """
    plan=json.loads((SOURCE/'study_plan.json').read_text())
    sample=pd.read_csv(SOURCE/'evaluation.csv',usecols=['timestamp'])
    timestamps=pd.to_datetime(sample.timestamp,utc=True,format='mixed')
    offsets=((timestamps-timestamps.min().normalize()).dt.total_seconds()//43200).astype(int)
    blocks=int(offsets.max())+1
    counts=np.bincount(offsets,minlength=blocks)
    runs=pd.read_csv(SOURCE/'main/run_metrics.csv')
    records=[]
    for replicate in range(1,50):
        seed=_seed_value(plan['seed'],0,replicate,0)
        rng=np.random.default_rng(np.random.SeedSequence(seed,spawn_key=(0,replicate,12)))
        choices=[int(rng.integers(max(0,t-6),min(blocks-1,t+6)+1)) for t in range(blocks)]
        expected=int(counts[choices].sum())
        assert runs[runs.replicate==replicate].request_count.eq(expected).all()
        records.append(dict(replicate=replicate,block_count=blocks,request_count=expected,
            block_choices_sha256=hashlib.sha256(np.asarray(choices,dtype='<i8').tobytes()).hexdigest()))
    result=pd.DataFrame(records)
    assert result.block_choices_sha256.is_unique
    return result


def build():
    if DEST.exists():raise SystemExit('Presentation study directory exists; refusing overwrite.')
    diagnostics=json.loads((SOURCE/'main/runtime.json').read_text())
    assert diagnostics['completed']
    runs=pd.read_csv(SOURCE/'main/run_metrics.csv')
    tenants=pd.read_csv(SOURCE/'main/tenant_metrics.csv')
    audit=pd.read_csv(SOURCE/'main/pairing_audit.csv')
    comparisons=pd.read_csv(SOURCE/'main/policy_comparisons.csv')
    baseline=runs[runs.policy=='FCFS'][['replicate','budget_micro_usd','request_count','completed_original','completion_rate_original','min_tenant_completion_rate']].rename(
        columns={'completed_original':'fcfs_completed','completion_rate_original':'fcfs_completion','min_tenant_completion_rate':'fcfs_minimum','request_count':'fcfs_demand'})
    data=runs.merge(baseline,on=['replicate','budget_micro_usd'],validate='many_to_one')
    assert data.request_count.eq(data.fcfs_demand).all()
    data=data.merge(audit[['scenario_id','policy','workload_hash','draw_hash','delivered_output_tokens']],on=['scenario_id','policy'],validate='one_to_one')
    data['completion_difference_pp']=100*(data.completion_rate_original-data.fcfs_completion)
    data['minimum_tenant_difference_pp']=100*(data.min_tenant_completion_rate-data.fcfs_minimum)
    check=data[data.policy!='FCFS'].merge(comparisons[['scenario_id','policy','paired_completed_original_difference']],on=['scenario_id','policy'],validate='one_to_one')
    assert (check.completed_original-check.fcfs_completed==check.paired_completed_original_difference).all()
    assert (data.completed_original+data.truncated+data.rejected==data.request_count).all()
    assert (data.realized_cost_micro_usd+data.budget_remaining_micro_usd==data.budget_micro_usd).all()
    assert data.overrun_micro_usd.eq(0).all() and data.completed_routed.eq(0).all()
    for _,g in data.groupby('replicate'):
        assert g.workload_hash.nunique()==g.draw_hash.nunique()==g.budget_micro_usd.nunique()==1
    stochastic=data[data.replicate>0]
    assert stochastic[stochastic.policy=='FCFS'].workload_hash.is_unique
    summary=[];effects=[]
    for policy,g in stochastic.groupby('policy'):
        replay=data[(data.policy==policy)&(data.replicate==0)].iloc[0]
        row=dict(policy=policy,resamples=len(g),replay_completion_pct=100*replay.completion_rate_original,
            median_completion_pct=100*g.completion_rate_original.median(),mean_completion_pct=100*g.completion_rate_original.mean(),
            median_rejection_pct=(100*g.rejected/g.request_count).median(),median_truncation_pct=(100*g.truncated/g.request_count).median(),
            median_budget_utilization_pct=100*g.budget_utilization.median(),median_min_tenant_completion_pct=100*g.min_tenant_completion_rate.median(),
            median_delivered_output_tokens=g.delivered_output_tokens.median(),median_delivered_output_per_demand=(g.delivered_output_tokens/g.request_count).median(),
            replay_min_tenant_completion_pct=100*replay.min_tenant_completion_rate,cap_exceeded_total=int(g.output_cap_exceeded_count.sum()))
        row.update({f'median_completion_q{i}_pct':100*g[f'completion_size_q{i}'].median() for i in range(1,5)})
        summary.append(row)
        values=g.completion_difference_pp;replay_effect=replay.completion_difference_pp
        effects.append(dict(policy=policy,resamples=len(g),replay_difference_pp=replay_effect,mean_difference_pp=values.mean(),
            median_difference_pp=values.median(),q25_difference_pp=values.quantile(.25),q75_difference_pp=values.quantile(.75),
            p05_difference_pp=values.quantile(.05),p95_difference_pp=values.quantile(.95),min_difference_pp=values.min(),max_difference_pp=values.max(),
            wins=int(values.gt(0).sum()),ties=int(values.eq(0).sum()),losses=int(values.lt(0).sum()),win_pct=100*values.gt(0).mean(),
            reversals_from_replay=int((np.sign(values)*np.sign(replay_effect)<0).sum()) if replay_effect else None,
            median_minimum_tenant_difference_pp=g.minimum_tenant_difference_pp.median()))
    tbase=tenants[tenants.policy=='FCFS'][['replicate','tenant','completion_rate_original']].rename(columns={'completion_rate_original':'fcfs_rate'})
    paired_tenants=tenants.merge(tbase,on=['replicate','tenant'],validate='many_to_one')
    paired_tenants['difference_pp']=100*(paired_tenants.completion_rate_original-paired_tenants.fcfs_rate)
    tenant_summary=[]
    for (tenant,policy),g in paired_tenants[paired_tenants.replicate>0].groupby(['tenant','policy']):
        replay=paired_tenants[(paired_tenants.tenant==tenant)&(paired_tenants.policy==policy)&(paired_tenants.replicate==0)].iloc[0]
        tenant_summary.append(dict(tenant=tenant,policy=policy,resamples=len(g),median_completion_pct=100*g.completion_rate_original.median(),
            median_difference_pp=g.difference_pp.median(),p05_difference_pp=g.difference_pp.quantile(.05),p95_difference_pp=g.difference_pp.quantile(.95),
            median_rejection_pct=(100*g.rejected/g.demand_requests).median(),median_truncation_pct=(100*g.truncated/g.demand_requests).median(),
            win_pct=100*g.difference_pp.gt(0).mean(),replay_completion_pct=100*replay.completion_rate_original,
            replay_difference_pp=replay.difference_pp))
    matrix=data.pivot(index='replicate',columns='policy',values='completion_rate_original')
    rankings=[]
    for a,b in combinations(sorted(matrix.columns),2):
        replay=matrix.loc[0,a]-matrix.loc[0,b];values=100*(matrix.loc[matrix.index>0,a]-matrix.loc[matrix.index>0,b])
        rankings.append(dict(policy_a=a,policy_b=b,replay_a_minus_b_pp=100*replay,resamples=len(values),
            a_wins=int(values.gt(0).sum()),ties=int(values.eq(0).sum()),b_wins=int(values.lt(0).sum()),
            strict_reversals=int((np.sign(values)*np.sign(replay)<0).sum()) if replay else None))
    replicate=data[['run_id','replicate','workload_kind','policy','request_count','completed_original','rejected','truncated',
        'completion_difference_pp','minimum_tenant_difference_pp','delivered_output_tokens']].copy()
    replicate['completion_pct']=100*data.completion_rate_original
    replicate['rejection_pct']=100*data.rejected/data.request_count;replicate['truncation_pct']=100*data.truncated/data.request_count
    replicate['budget_utilization_pct']=100*data.budget_utilization;replicate['min_tenant_completion_pct']=100*data.min_tenant_completion_rate
    replicate['spend_usd']=data.realized_cost_micro_usd/1e6;replicate['budget_usd']=data.budget_micro_usd/1e6
    tables={'policy_summary':pd.DataFrame(summary),'paired_effects':pd.DataFrame(effects),'tenant_outcomes':pd.DataFrame(tenant_summary),
        'replicate_results':replicate,'sampling_audit':pd.read_csv(SOURCE/'sampling_audit.csv'),'ranking_stability':pd.DataFrame(rankings),
        'block_draw_audit':block_draw_audit()}
    quantile=SOURCE/'quantile'
    if (quantile/'runtime.json').exists():
        sensitivity=pd.read_csv(quantile/'run_metrics.csv')
        saudit=pd.read_csv(quantile/'pairing_audit.csv')
        sensitivity=sensitivity.merge(saudit[['scenario_id','policy','workload_hash','draw_hash']],on=['scenario_id','policy'],validate='one_to_one')
        reference=sensitivity[sensitivity.policy=='FCFS'][['replicate','completion_rate_original']].rename(columns={'completion_rate_original':'q_fcfs'})
        sensitivity=sensitivity.merge(reference,on='replicate',validate='many_to_one')
        matched=sensitivity.merge(data,on=['replicate','policy'],suffixes=('_q','_mean'),validate='one_to_one')
        assert matched.workload_hash_q.eq(matched.workload_hash_mean).all()
        assert matched.draw_hash_q.eq(matched.draw_hash_mean).all()
        assert matched.budget_micro_usd_q.eq(matched.budget_micro_usd_mean).all()
        rows=[]
        for policy,g in matched[matched.replicate>0].groupby('policy'):
            q_effect=100*(g.completion_rate_original_q-g.q_fcfs)
            mean_effect=g.completion_difference_pp
            rows.append(dict(policy=policy,resamples=len(g),mean_reservation_median_completion_pct=100*g.completion_rate_original_mean.median(),
                quantile_reservation_median_completion_pct=100*g.completion_rate_original_q.median(),
                mean_reservation_median_truncation_pct=(100*g.truncated_mean/g.request_count_mean).median(),
                quantile_reservation_median_truncation_pct=(100*g.truncated_q/g.request_count_q).median(),
                mean_reservation_median_rejection_pct=(100*g.rejected_mean/g.request_count_mean).median(),
                quantile_reservation_median_rejection_pct=(100*g.rejected_q/g.request_count_q).median(),
                mean_reservation_paired_median_pp=mean_effect.median(),quantile_reservation_paired_median_pp=q_effect.median(),
                quantile_reservation_paired_p05_pp=q_effect.quantile(.05),quantile_reservation_paired_p95_pp=q_effect.quantile(.95),
                paired_sign_changes=int((np.sign(q_effect)*np.sign(mean_effect)<0).sum())))
        tables['reservation_sensitivity']=pd.DataFrame(rows)
    plan=json.loads((SOURCE/'study_plan.json').read_text())
    for path,expected in plan['protected_hashes'].items():assert sha(ROOT/path)==expected,path
    DEST.mkdir(parents=True)
    for name,frame in tables.items():frame.to_csv(DEST/f'{name}.csv',index=False,float_format='%.12g',lineterminator='\n')
    # No original presentation file or manifest is updated.
    verification=dict(label='MODELED OCTOBER SUBSET; synthetic competition telemetry',replay_separate=True,
        resamples=int(stochastic.replicate.nunique()),policy_runs=len(data),source_requests=plan['evaluation_requests'],
        min_resampled_requests=int(stochastic.request_count.min()),max_resampled_requests=int(stochastic.request_count.max()),
        pairing_hashes_verified=True,distinct_workload_hashes=True,budget_conservation=True,outcome_conservation=True,
        protected_files_unchanged=len(plan['protected_hashes']),training_window=plan['sample_train_window'],evaluation_window=plan['sample_eval_window'],
        data_files={name+'.csv':dict(rows=len(frame),sha256=sha(DEST/f'{name}.csv')) for name,frame in tables.items()},runtime=diagnostics,
        interpretation='Medians, IQR and 5th-95th percentiles describe conditional resampled outcomes, not real-world confidence intervals.')
    (SOURCE/'verification.json').write_text(json.dumps(verification,indent=2)+'\n',encoding='utf-8')
    (DEST/'provenance.json').write_text(json.dumps(dict(study_plan=plan,runtime=diagnostics,verification=verification),indent=2)+'\n',encoding='utf-8')
    print(tables['policy_summary'].to_string(index=False));print(tables['paired_effects'].to_string(index=False))
    print('TENANTS');print(tables['tenant_outcomes'].pivot(index='tenant',columns='policy',values='median_difference_pp').round(3).to_string())
    if 'reservation_sensitivity' in tables:print(tables['reservation_sensitivity'].to_string(index=False))
    return tables


if __name__=='__main__':build()
