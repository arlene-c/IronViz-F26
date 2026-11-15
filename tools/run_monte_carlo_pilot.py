"""One bounded exploratory synthetic pilot: 2000 rows, 30 replicates, 3 policies.

No raw input, historical export, trace file, or figure is read/written. Existing
destination directories are rejected. Run from the repository root.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import pandas as pd

from ironviz_f26.cli import synthetic_catalog
from ironviz_f26.experiments import ExperimentConfig, ExperimentRunner
from ironviz_f26.fixture import generate_fixture
from ironviz_f26.pricing import PriceCatalog


def main():
    root=Path(__file__).resolve().parents[1]
    destination=root/'outputs/monte_carlo_pilot'
    if destination.exists():
        raise SystemExit('Pilot directory already exists; refusing to overwrite or rerun.')
    seed=20261114
    rows=generate_fixture(seed=seed,n_requests=2000,requests_per_day=100)
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    # Equal-sized complete 12h blocks avoid empty/partial-block artifacts from
    # the fixture generator's default first-hour-of-day burst timestamps.
    for index,row in enumerate(rows):
        row['timestamp']=(start+timedelta(seconds=index*864)).isoformat()
    base=synthetic_catalog()
    catalog=PriceCatalog('SYNTHETIC PILOT ONLY; fixture prices x1000, not historical rates',
        {pair:replace(price,input_price=price.input_price*1000,cached_input_price=price.cached_input_price*1000,
                      output_price=price.output_price*1000) for pair,price in base._rows.items()})
    config=ExperimentConfig(budget_fractions=(.7,),replicates=30,seed=seed,training_fraction=.2,
        bootstrap=True,bootstrap_method='local_12h',bootstrap_block_hours=12,bootstrap_window_days=3.,
        demand_imbalance=(1.,),estimator_noise=(0.,),routing_eligibility=(0.,),
        reservation_multipliers=(1.,),routed_output_multipliers=(1.,),
        policies=('FCFS','Adaptive','Pacing'),trace_replicates=(),trace_policies=(),timeseries_stride=100,
        tenant_roster=('tenant-a','tenant-b','tenant-c'),
        horizon_start='2026-01-05T00:00:00Z',horizon_end='2026-01-21T00:00:00Z',
        data_label='EXPLORATORY SYNTHETIC MONTE CARLO PILOT; not institutional evidence')
    assert len(rows)==2000 and len(config.policies)*config.replicates==90
    started=time.perf_counter()
    result=ExperimentRunner(catalog,config).run(rows)
    runtime=time.perf_counter()-started
    runs=result.run_metrics
    assert len(runs)==90 and result.event_traces.empty
    assert runs.groupby('replicate').size().eq(3).all()
    assert runs.request_count.eq(1600).all()
    assert runs.completed_routed.eq(0).all() and runs.overrun_micro_usd.eq(0).all()
    assert (runs.completed_original+runs.rejected+runs.truncated==runs.request_count).all()
    assert (runs.realized_cost_micro_usd+runs.budget_remaining_micro_usd==runs.budget_micro_usd).all()
    baseline=runs[runs.policy=='FCFS'][['scenario_id','replicate','completion_rate_original']].rename(columns={'completion_rate_original':'fcfs_completion_rate'})
    rates=runs[['run_id','scenario_id','replicate','workload_kind','policy','request_count','completed_original',
                'completion_rate_original','min_tenant_completion_rate','budget_utilization','rejected','truncated']].merge(
                    baseline,on=['scenario_id','replicate'],validate='many_to_one')
    rates['paired_completion_rate_difference_pp']=100*(rates.completion_rate_original-rates.fcfs_completion_rate)
    resamples=rates[rates.replicate>0]
    effects=[]
    for policy,group in resamples.groupby('policy'):
        values=group.paired_completion_rate_difference_pp
        effects.append(dict(policy=policy,resamples=len(group),median_pp=values.median(),q25_pp=values.quantile(.25),
            q75_pp=values.quantile(.75),min_pp=values.min(),max_pp=values.max(),p025_pp=values.quantile(.025),
            p975_pp=values.quantile(.975),wins=int((values>0).sum()),ties=int((values==0).sum()),losses=int((values<0).sum())))
    matrix=rates.pivot(index='replicate',columns='policy',values='completion_rate_original')
    reversals=[]
    for a,b in [('Adaptive','FCFS'),('Pacing','FCFS'),('Pacing','Adaptive')]:
        reference=np.sign(matrix.loc[0,a]-matrix.loc[0,b]); differences=matrix.loc[matrix.index>0,a]-matrix.loc[matrix.index>0,b]
        reversals.append(dict(pair=f'{a} minus {b}',replay_difference_pp=100*(matrix.loc[0,a]-matrix.loc[0,b]),
            strict_reversals=int((np.sign(differences)*reference<0).sum()) if reference else None,
            resample_ties=int(differences.eq(0).sum()),resamples=29))
    metadata=result.scenario_metadata
    metadata.update(pilot_runtime_seconds=runtime,source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        source_branch='simulation-validation; working-tree corrections documented in documentation/VALIDATION.md',
        input_request_count=2000,simulation_run_count=90,retimed_fixture='100 requests/day uniformly spaced; 50 per 12-hour block; training first 4 days',
        synthetic_price_scaling='fixture rates multiplied by 1000 to reduce component-rounding dominance; not real prices',
        interpretation='29 conditional workload resamples plus separate replay; percentile ranges are descriptive synthetic outcome spread, not full-data confidence intervals',
        verification='90 runs; 1600 evaluation requests each; no retained event traces; outcomes/budgets reconcile; no routing/overrun')
    destination.mkdir(parents=True)
    for name,frame in [('run_metrics',runs),('tenant_metrics',result.tenant_metrics),('experiment_summary',result.experiment_summary),
                       ('policy_comparisons',result.policy_comparisons),('policy_completion_rates',rates),
                       ('paired_effect_summary',pd.DataFrame(effects)),('ranking_reversals',pd.DataFrame(reversals))]:
        frame.to_csv(destination/f'{name}.csv',index=False)
    (destination/'scenario_metadata.json').write_text(json.dumps(metadata,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps(dict(label=config.data_label,runtime_seconds=runtime,runs=len(runs),retained_event_traces=len(result.event_traces),
                          effects=effects,reversals=reversals),indent=2))


if __name__=='__main__':
    main()
