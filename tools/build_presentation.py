"""Build small presentation tables from saved CSVs only. No simulator imports."""
from pathlib import Path
from itertools import combinations
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'results/presentation'

DESCRIPTIONS = {'dataset': ('label',
             'Historical October replay/probe or fictional synthetic pilot; never pool these '
             'populations.'),
 'result_status': ('label', 'historical_pre_correction_provisional or exploratory_synthetic.'),
 'policy': ('label',
            'FCFS, Quotas (equal dollars), TrainingQuotas, Adaptive, Pacing or Threshold.'),
 'budget_pct': ('percent',
                'Modeled budget as a percentage of original-model reference expenditure for that '
                'workload.'),
 'source_run_id': ('identifier',
                   'Original saved run identifier; scope with dataset and bootstrap_method when '
                   'present.'),
 'request_count': ('requests',
                   'Demand denominator: evaluation requests, or tenant evaluation requests in the '
                   'tenant table.'),
 'completed_requests': ('requests',
                        'Fully completed original requests; excludes truncations and '
                        'counterfactual routing.'),
 'completion_pct': ('percent', '100 times completed_requests/request_count.'),
 'truncated_requests': ('requests',
                        'Admitted executions that did not finish their original observed output.'),
 'truncation_pct': ('percent', '100 times truncated_requests/request_count.'),
 'rejected_requests': ('requests',
                       'Requests denied execution; disjoint from completed and truncated.'),
 'rejection_pct': ('percent', '100 times rejected_requests/request_count.'),
 'admitted_requests': ('requests',
                       'Completed plus truncated executions; not fully served requests.'),
 'budget_usd': ('modeled USD',
                'Global budget converted from integer micro-USD; not an actual bill.'),
 'spend_usd': ('modeled USD', 'Realized execution expenditure, including truncated executions.'),
 'unused_budget_usd': ('modeled USD',
                       'Global budget minus execution expenditure; not unused reservations.'),
 'budget_utilization_pct': ('percent', '100 times expenditure/global budget.'),
 'fcfs_completed_requests': ('requests',
                             'Completed requests for the matching FCFS workload, budget and '
                             'replicate; tenant-specific in tenant table.'),
 'fcfs_completion_pct': ('percent', 'Completion percentage for the matching FCFS baseline.'),
 'completion_difference_requests': ('requests',
                                    'Policy completed count minus matching FCFS completed count.'),
 'completion_difference_pp': ('percentage points',
                              'Policy completion percentage minus matching FCFS percentage; not '
                              'relative percent change.'),
 'spend_difference_usd': ('modeled USD',
                          'Policy spend minus matching FCFS spend; negative means lower '
                          'expenditure.'),
 'utilization_difference_pp': ('percentage points',
                               'Policy budget utilization minus matching FCFS utilization.'),
 'min_tenant_completion_pct': ('percent',
                               'Lowest completion percentage among operational tenants; not '
                               'demographic fairness.'),
 'tenant_completion_gap_pp': ('percentage points',
                              'Highest tenant completion rate minus lowest tenant completion '
                              'rate.'),
 'tenant': ('identifier',
            'Operational billing/project group, not an individual or demographic group.'),
 'bootstrap_method': ('label',
                      'local_12h: 12-hour blocks within +/-3 days; day_block: whole-day '
                      'resampling.'),
 'replicate': ('integer', '0 is original replay; positive values identify resampled workloads.'),
 'workload_kind': ('label',
                   'replay, local_12h_block_bootstrap or day_block_bootstrap; keep replay '
                   'separate.'),
 'resamples': ('workloads', 'Number of positive-replicate paired observations; excludes replay.'),
 'wins': ('workloads', 'Resamples where policy completion rate exceeds FCFS.'),
 'ties': ('workloads',
          'Resamples with equal policy and FCFS completion rates; all FCFS rows tie themselves.'),
 'losses': ('workloads', 'Resamples where policy completion rate is below FCFS.'),
 'win_pct': ('percent',
             '100 times wins/resamples; conditional frequency, not real-world success '
             'probability.'),
 'replay_completion_pct': ('percent',
                           'Policy completion percentage in the separate original replay.'),
 'median_completion_pct': ('percent', 'Median policy completion percentage across resamples.'),
 'median_min_tenant_completion_pct': ('percent',
                                      "Median of each resample's minimum tenant completion "
                                      'percentage.'),
 'median_budget_utilization_pct': ('percent', 'Median policy budget utilization across resamples.')}


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


SOURCE=ROOT/'results/monte_carlo'


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
    runs=pd.read_csv(SOURCE/'main_run_metrics.csv')
    records=[]
    for replicate in range(1,50):
        seed=int(np.random.SeedSequence(plan['seed'],spawn_key=(0,replicate,0)).generate_state(1,dtype=np.uint32)[0])
        rng=np.random.default_rng(np.random.SeedSequence(seed,spawn_key=(0,replicate,12)))
        choices=[int(rng.integers(max(0,t-6),min(blocks-1,t+6)+1)) for t in range(blocks)]
        expected=int(counts[choices].sum())
        assert runs[runs.replicate==replicate].request_count.eq(expected).all()
        records.append(dict(replicate=replicate,block_count=blocks,request_count=expected,
            block_choices_sha256=hashlib.sha256(np.asarray(choices,dtype='<i8').tobytes()).hexdigest()))
    result=pd.DataFrame(records)
    assert result.block_choices_sha256.is_unique
    return result


def october_tables():
    diagnostics=json.loads((SOURCE/'main_runtime.json').read_text())
    assert diagnostics['completed']
    runs=pd.read_csv(SOURCE/'main_run_metrics.csv')
    tenants=pd.read_csv(SOURCE/'main_tenant_metrics.csv')
    audit=pd.read_csv(SOURCE/'main_pairing_audit.csv')
    comparisons=pd.read_csv(SOURCE/'main_policy_comparisons.csv')
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
        'replicate_results':replicate,'sampling_audit':pd.read_csv(SOURCE/'sampling_audit.csv'),'ranking_stability':pd.DataFrame(rankings)}
    pd.testing.assert_frame_equal(block_draw_audit(),pd.read_csv(SOURCE/'block_draw_audit.csv'))
    if (SOURCE/'quantile_runtime.json').exists():
        sensitivity=pd.read_csv(SOURCE/'quantile_run_metrics.csv')
        saudit=pd.read_csv(SOURCE/'quantile_pairing_audit.csv')
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
    return tables


def column_description(column):
    """Units and definitions shared by all presentation tables."""
    special={
        'result_status':('label','descriptive_synthetic, historical_pre_correction_provisional, or corrected_modeled_subset; never pool these populations.'),
        'reservation_mode':('label','mean, or mean_vs_q90 for the matched ten-resample reservation comparison.'),
        'completed_requests':('requests','Fully completed original requests; excludes partial output and rejected requests.'),
        'resamples':('workloads','Positive replicate count only; separate replay is excluded.'),
        'population':('label','training or evaluation population in the sampling audit.'),
        'metric':('label','Marginal share, token statistic or modeled reference cost audited against the original population.'),
        'category':('label','Tenant/model/calendar category or statistic within the audited metric.'),
        'source_value':('see unit','Statistic for the original source population.'),
        'subset_value':('see unit','Same statistic for the fixed selected subset.'),
        'difference':('see unit','Subset minus source statistic; share differences are percentage points.'),
        'unit':('label','Units of source/subset/difference; percentages use pp for their differences.'),
        'policy_a':('label','First policy in the pairwise ranking comparison.'),
        'policy_b':('label','Second policy in the pairwise ranking comparison.'),
        'strict_reversals':('workloads','Strict opposite ordering from replay; ties excluded.'),
        'reversals_from_replay':('workloads','Strict sign reversals of policy-minus-FCFS effect relative to replay.'),
        'paired_sign_changes':('workloads','Matched resamples whose policy-minus-FCFS effect changes strict sign between mean and Q90 reservations.'),
        'a_wins':('workloads','Resamples in which policy_a has more full completions than policy_b.'),
        'b_wins':('workloads','Resamples in which policy_b has more full completions than policy_a.'),
        'cap_exceeded_total':('admissions','Sum of admitted executions exceeding the model cap across resamples; not all demand.'),
        'block_count':('blocks','Number of target 12-hour calendar blocks.'),
        'block_choices_sha256':('SHA-256','Hash of the source-block index sequence, independent of replicate-specific request IDs.'),
        'median_delivered_output_tokens':('output tokens','Median delivered output including partial outputs; not task utility.'),
        'median_delivered_output_per_demand':('output tokens/request','Median delivered output divided by all demand, including rejected requests.'),
        'delivered_output_tokens':('output tokens','Total delivered output including partial outputs from truncated executions.'),
        'provider':('label','Synthetic telemetry provider label.'),
        'model':('label','Recorded original model identifier.'),
        'calls':('requests','Eligible successful requests for model/weekly tables; operational calls excluding invalid records for tenant/daily tables.'),
        'successful_calls':('requests','Eligible successful requests for this tenant.'),
        'tokens':('input + output tokens','Total original input plus output tokens for eligible requests; no utility weighting.'),
        'median_prompt_tokens':('input tokens','Median original prompt length among eligible requests.'),
        'testing_team':('boolean','Source-defined testing group: engineering-dev and sandbox-testing; not a demographic category.'),
        'week':('calendar interval','October 1-7, 8-14, 15-21 or 22-30; final interval has nine days.'),
        'day':('day of October','Calendar day in October 2026 UTC.'),
        'rate_limited_429':('requests','Calls with HTTP 429; observational telemetry outcome, not simulated budget rejection.'),
        'bad_request_400':('requests','Calls with HTTP 400; not simulated budget rejection.'),
    }
    if column in special:return special[column]
    if column in DESCRIPTIONS:return DESCRIPTIONS[column]
    if column.endswith('_pct'):
        definitions={
            'premium_model_pct':'Share of eligible calls on gpt-4o, o1-preview or gemini-1.5-pro.',
            'calls_using_cache_pct':'Eligible requests with any cached input divided by eligible requests.',
            'cached_share_of_input_pct':'Cached input tokens divided by total input tokens.',
            'bad_request_pct':'HTTP 400 calls divided by operational calls, excluding invalid telemetry records.',
            'rate_limited_pct':'HTTP 429 calls divided by operational calls, excluding invalid telemetry records.',
            'call_share_pct':'Share of eligible model requests or operational tenant calls, according to table grain.',
            'cost_share_pct':'Share of reconstructed floating-price expenditure among eligible requests.',
            'token_share_pct':'Share of eligible original input plus output tokens.',
        }
        meaning=definitions.get(column,column.removesuffix('_pct').replace('_',' ')+'; completion/truncation/rejection rates use all demand; quartiles use original input + output tokens.')
        return 'percent (0-100)',meaning
    if column.endswith('_pp'):
        return 'percentage points',column.removesuffix('_pp').replace('_',' ')+'; paired against the SAME replicate FCFS unless policy_a/policy_b is specified. Quantiles summarize resamples, not real-world confidence bounds.'
    if column.endswith('_usd'):
        return 'modeled USD',column.removesuffix('_usd').replace('_',' ')+'; no verified invoice or price-effective-date claim.'
    raise ValueError(f'Undocumented column: {column}')


def build():
    """Rebuild all chart tables using versioned saved inputs, never policy code."""
    global SOURCE
    SOURCE=ROOT/'results/monte_carlo'
    canonical=ROOT/'results/canonical'
    protected={p.relative_to(ROOT).as_posix():digest(p) for p in canonical.rglob('*') if p.is_file()}
    inputs={}
    def read(relative):
        path=ROOT/relative;inputs[relative]=digest(path)
        return pd.read_csv(path)
    tables={
        'policy_budget_summary.csv':historical_table(read('results/canonical/policies/run_metrics.csv'),'historical_october_replay'),
        'tenant_tradeoffs_70pct.csv':tenant_table(read('results/canonical/policies/tenant_metrics.csv')),
    }
    probes=[]
    for folder,method in [('local_bootstrap','local_12h'),('day_bootstrap','day_block')]:
        raw=read(f'results/canonical/{folder}/run_metrics.csv')
        table=historical_table(raw,'historical_bootstrap_probe')
        table['bootstrap_method']=method
        table['replicate']=raw.replicate.to_numpy();table['workload_kind']=raw.workload_kind.to_numpy()
        probes.append(table)
    tables['bootstrap_methods_70pct.csv']=pd.concat(probes,ignore_index=True)
    for filename in ('analysis_cost_by_model.csv','analysis_team_summary.csv','analysis_weekly_trend.csv','analysis_rate_limits_daily.csv'):
        frame=read('results/'+filename)
        frame.insert(0,'result_status','descriptive_synthetic')
        frame.insert(0,'dataset','synthetic_october_telemetry')
        tables['descriptive_'+filename.removeprefix('analysis_')]=frame
    for name,frame in october_tables().items():
        frame=frame.rename(columns={'completed_original':'completed_requests','rejected':'rejected_requests','truncated':'truncated_requests','run_id':'source_run_id'})
        frame.insert(0,'reservation_mode','mean_vs_q90' if name=='reservation_sensitivity' else 'mean')
        frame.insert(0,'budget_pct',70)
        frame.insert(0,'result_status','corrected_modeled_subset')
        frame.insert(0,'dataset','modeled_october_subset')
        tables['monte_carlo/'+name+'.csv']=frame
    for folder in (SOURCE,):
        for path in folder.iterdir():
            if path.is_file():inputs[path.relative_to(ROOT).as_posix()]=digest(path)
    assert len(tables['policy_budget_summary.csv'])==24
    assert len(tables['tenant_tradeoffs_70pct.csv'])==36
    assert len(tables['bootstrap_methods_70pct.csv'])==24
    assert len(tables['monte_carlo/replicate_results.csv'])==300
    for name,frame in tables.items():
        assert not frame.empty
        if 'completed_requests' in frame and 'truncated_requests' in frame:
            assert (frame.completed_requests+frame.truncated_requests+frame.rejected_requests==frame.request_count).all()
        if 'unused_budget_usd' in frame:
            assert np.allclose(frame.spend_usd+frame.unused_budget_usd,frame.budget_usd)
        for column in frame:column_description(column)
    DEST.mkdir(parents=True,exist_ok=True)
    dictionary=['# Presentation data dictionary','',
        'One entry point for chart-ready data. Every CSV carries dataset and result_status labels.',
        'Historical October replay: 154,278 evaluation requests; pre-correction and provisional.',
        'Corrected October subset: 5,000 evaluation requests; separate replay + 49 resamples; all rates use all demand.',
        'Descriptive telemetry: full synthetic month, floating-price reconstruction; observed synthetic usage, not simulated outcomes.',
        'Reservation sensitivity: ten matched resamples, mean versus Q90; three policies only.',
        'Percentages are already 0-100. Percentage points are absolute rate differences. USD is modeled, not billed.',
        'Delivered output includes truncated output and does not measure usefulness. Ranges are conditional spreads, not real-world confidence intervals.','',
        'Historical key: (policy, budget_pct); tenant key: (tenant, policy); bootstrap key: (bootstrap_method, replicate, policy).',
        'Monte Carlo key: (replicate, policy). Replicate 0 is replay, excluded from summary distributions.',
        'Historical bootstrap methods each contain the SAME replay plus ONE resample. Never pool those with the corrected study.','']
    for name,frame in tables.items():
        target=DEST/name;target.parent.mkdir(parents=True,exist_ok=True)
        frame.to_csv(target,index=False,float_format='%.12g',lineterminator='\n')
        dictionary.extend([f'## {name}','',f'{len(frame)} rows. Source hashes: [provenance.json](provenance.json).','',
                           '| Column | Unit | Definition |','|---|---|---|'])
        dictionary.extend(f'| `{column}` | {column_description(column)[0]} | {column_description(column)[1]} |' for column in frame)
        dictionary.append('')
    (DEST/'data_dictionary.md').write_text('\n'.join(dictionary).rstrip()+'\n',encoding='utf-8')
    for relative,expected in {**protected,**inputs}.items():assert digest(ROOT/relative)==expected,relative
    provenance=dict(generator='tools/build_presentation.py; saved-table aggregation only; no simulation imports',
        historical_status='pre-correction provisional; canonical manifest and bytes unchanged',
        monte_carlo_status='corrected modeled subset; synthetic telemetry; conditional resampling distributions',
        source_sha256=inputs,canonical_sha256=protected,
        outputs={name:dict(rows=len(frame),columns=list(frame.columns),sha256=digest(DEST/name)) for name,frame in tables.items()})
    (DEST/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    print('\n'.join(f'{name}: {len(frame)} rows' for name,frame in tables.items()))
    return tables


if __name__=='__main__':build()
