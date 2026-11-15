"""Bounded October subset study. No historical workload is ever simulated.

Stages are explicit; pilots must be inspected before main. Each worker has a
300-second timeout and 512-MiB process memory ceiling. Existing stages never
overwrite. Main is <=50 replicates, <=8000 events per policy run, one budget.
"""
import argparse
from collections import defaultdict
from dataclasses import asdict
import hashlib
import json
import math
import os
import signal
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ironviz_f26.cli import load_catalog
from ironviz_f26.engine import SimulationEngine
from ironviz_f26.estimators import GlobalEstimator
from ironviz_f26.experiments import ExperimentConfig, ExperimentRunner
from ironviz_f26.policies import FCFS
from ironviz_f26.money import Money

BASE=ROOT/'outputs/monte_carlo_october'
SEED=20261115
CAPS={model:8192 for model in ('gpt-4o','gpt-4o-mini','o1-preview','gemini-1.5-pro','gemini-1.5-flash')}
POLICIES=('FCFS','Quotas','TrainingQuotas','Adaptive','Pacing','Threshold')
HORIZON=('2026-10-07T00:00:00Z','2026-10-31T00:00:00Z')
MEMORY_LIMIT=512*1024*1024


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path,value):
    Path(path).write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf-8')


def memory(pid=None):
    if os.name!='nt':
        import resource
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024) if pid is None else None
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in
          ('peak','working','peak_pool','pool','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
    psapi.GetProcessMemoryInfo.argtypes=(wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD)
    handle=kernel.OpenProcess(0x0410,False,pid) if pid else kernel.GetCurrentProcess()
    if not handle:return None
    try:
        values=Counters();values.cb=ctypes.sizeof(values)
        return int(values.peak) if psapi.GetProcessMemoryInfo(handle,ctypes.byref(values),values.cb) else None
    finally:
        if pid:kernel.CloseHandle(handle)


def stratified(frame,count,stream):
    """Largest-remainder proportional allocation over time x tenant x model x cache."""
    assert 0<count<=len(frame)
    keys=pd.DataFrame(dict(block=pd.to_datetime(frame.timestamp,utc=True,format='mixed').dt.floor('12h'),
        tenant=frame.tenant,provider=frame.provider,model=frame.model,cache=frame.cached_input_tokens.gt(0)))
    groups=keys.groupby(list(keys.columns),sort=True,observed=True).indices
    names=list(groups);sizes=np.array([len(groups[k]) for k in names]);ideal=sizes*count/len(frame)
    allocations=np.floor(ideal).astype(int)
    order=sorted(range(len(names)),key=lambda i:(-(ideal[i]-allocations[i]),i))
    for i in order[:count-int(allocations.sum())]:allocations[i]+=1
    rng=np.random.default_rng(np.random.SeedSequence(SEED,spawn_key=(10,stream)))
    indices=np.concatenate([rng.choice(groups[k],size=int(n),replace=False) for k,n in zip(names,allocations) if n])
    result=frame.iloc[indices].sort_values(['timestamp','request_id']).reset_index(drop=True)
    assert len(result)==count and result.request_id.is_unique
    return result


def costs(frame,catalog):
    result=np.zeros(len(frame),dtype=np.int64)
    for (provider,model),positions in frame.groupby(['provider','model']).indices.items():
        price=catalog.lookup(provider,model);g=frame.iloc[positions]
        inputs=g.input_tokens.to_numpy(dtype=np.int64);cached=g.cached_input_tokens.to_numpy(dtype=np.int64)
        output=g.output_tokens.to_numpy(dtype=np.int64)
        result[positions]=sum((tokens*rate+999999)//1000000 for tokens,rate in
            ((inputs-cached,price.input_price),(cached,price.cached_input_price),(output,price.output_price)))
    return result


def audit(source,subset,population,catalog):
    rows=[]
    def add(metric,category,a,b,unit):rows.append(dict(population=population,metric=metric,category=category,source_value=a,subset_value=b,difference=b-a,unit=unit))
    for column in ('tenant','provider','model'):
        for category in sorted(source[column].unique()):
            add(column,category,100*source[column].eq(category).mean(),100*subset[column].eq(category).mean(),'percent; difference in pp')
    for label,transform in [('day',lambda f:pd.to_datetime(f.timestamp,utc=True,format='mixed').dt.strftime('%Y-%m-%d')),
                             ('hour',lambda f:pd.to_datetime(f.timestamp,utc=True,format='mixed').dt.hour)]:
        a,b=transform(source),transform(subset)
        for category in sorted(a.unique()):add(label,str(category),100*a.eq(category).mean(),100*b.eq(category).mean(),'percent; difference in pp')
    add('cache_used','any',100*source.cached_input_tokens.gt(0).mean(),100*subset.cached_input_tokens.gt(0).mean(),'percent; difference in pp')
    premium={'gpt-4o','o1-preview','gemini-1.5-pro'}
    add('premium_model','premium',100*source.model.isin(premium).mean(),100*subset.model.isin(premium).mean(),'percent; difference in pp')
    for col in ('input_tokens','output_tokens'):
        add(col,'mean',source[col].mean(),subset[col].mean(),'tokens')
        for q in (.25,.5,.75,.9,.99,1.):add(col,f'q{q:g}',source[col].quantile(q),subset[col].quantile(q),'tokens')
    add('reference_cost','per request',costs(source,catalog).mean()/1e6,costs(subset,catalog).mean()/1e6,'modeled USD/request')
    return rows


def prepare():
    if BASE.exists():raise SystemExit('Study directory exists; refusing to overwrite.')
    source=ROOT/'outputs/canonical_reference/canonical_requests.csv'
    catalog_path=ROOT/'results/canonical/configuration/price_catalog_micro_usd.json'
    catalog=load_catalog(catalog_path)
    frame=pd.read_csv(source)
    assert len(frame)==192847 and frame.original_status.eq('success').all()
    frame['timestamp']=pd.to_datetime(frame.timestamp,utc=True,format='mixed').dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    original_train=frame.iloc[:38569].reset_index(drop=True);evaluation=frame.iloc[38569:].reset_index(drop=True)
    train=stratified(original_train,1250,0);sample=stratified(evaluation,5000,1);tiny=stratified(evaluation,500,2)
    assert train.timestamp.max()<sample.timestamp.min() and not set(train.request_id)&set(sample.request_id)
    assert set(sample.tenant)==set(evaluation.tenant)
    BASE.mkdir(parents=True)
    for name,data in [('training',train),('evaluation',sample),('tiny_evaluation',tiny)]:data.to_csv(BASE/f'{name}.csv',index=False)
    pd.DataFrame(audit(evaluation,sample,'evaluation',catalog)+audit(original_train,train,'training',catalog)).to_csv(BASE/'sampling_audit.csv',index=False)
    means=train.groupby(['provider','model']).output_tokens.mean();q90=train.groupby(['provider','model']).output_tokens.quantile(.9)
    caps=[]
    for (provider,model),g in sample.groupby(['provider','model']):
        estimate=math.ceil(means.loc[(provider,model)])
        caps.append(dict(provider=provider,model=model,requests=len(g),selected_cap=CAPS[model],training_mean_output=means.loc[(provider,model)],
            training_q90_output=q90.loc[(provider,model)],actual_mean_output=g.output_tokens.mean(),actual_median_output=g.output_tokens.median(),
            actual_p90_output=g.output_tokens.quantile(.9),actual_p99_output=g.output_tokens.quantile(.99),actual_max_output=g.output_tokens.max(),
            above_1024_pct=100*g.output_tokens.gt(1024).mean(),above_selected_cap_pct=100*g.output_tokens.gt(CAPS[model]).mean(),
            above_training_mean_pct=100*g.output_tokens.gt(estimate).mean(),mean_prediction_error_tokens=estimate-g.output_tokens.mean(),
            mean_absolute_prediction_error_tokens=(g.output_tokens-estimate).abs().mean()))
    pd.DataFrame(caps).to_csv(BASE/'output_cap_audit.csv',index=False)
    sanity=stratified(sample,64,3).to_dict('records');reports=[]
    budget=0
    for row in sanity:
        record=catalog.lookup(row['provider'],row['model']);cached=int(row['cached_input_tokens'])
        budget+=Money.cost_for_tokens(int(row['input_tokens'])-cached,record.input_price)+Money.cost_for_tokens(cached,record.cached_input_price)+Money.cost_for_tokens(8192,record.output_price)
    for mode,cap in [('mean',1024),('mean',8192),('quantile',8192)]:
        estimates={}
        for row in sanity:
            pair=(row['provider'],row['model']);price=catalog.lookup(*pair);cached=int(row['cached_input_tokens'])
            estimate=min(cap,math.ceil((means if mode=='mean' else q90).loc[pair]))
            estimates[(row['request_id'],*pair)]=Money.cost_for_tokens(int(row['input_tokens'])-cached,price.input_price)+Money.cost_for_tokens(cached,price.cached_input_price)+Money.cost_for_tokens(estimate,price.output_price)
        engine=SimulationEngine(catalog,FCFS(),budget,GlobalEstimator([0]),output_cap=cap)
        events=engine.run(sanity,estimated_costs=estimates)
        reports.append(dict(mode=mode,cap=cap,requests=64,completed=sum(e.outcome=='COMPLETED_ORIGINAL' for e in events),
            truncated=sum(e.outcome=='TRUNCATED_ORIGINAL' for e in events),rejected=sum(e.outcome=='REJECTED' for e in events),
            cap_exceeded=sum(e.output_cap_exceeded for e in events),reservation_shortfall=sum(e.reservation_shortfall for e in events)))
    pd.DataFrame(reports).to_csv(BASE/'cap_reservation_sanity.csv',index=False)
    protected={p.relative_to(ROOT).as_posix():sha(p) for folder in ('results/canonical','results/presentation','figures')
        for p in (ROOT/folder).rglob('*') if p.is_file()}
    protected['outputs/authoritative_policies/run_metrics.csv']=sha(ROOT/'outputs/authoritative_policies/run_metrics.csv')
    dump(BASE/'study_plan.json',dict(seed=SEED,training_requests=1250,evaluation_requests=5000,original_training_requests=38569,
        original_evaluation_requests=len(evaluation),source_sha256=sha(source),catalog_sha256=sha(catalog_path),source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        caps=CAPS,horizon=HORIZON,tenants=sorted(sample.tenant.unique()),max_events_per_run=8000,max_replicates=50,
        worker_memory_limit_mib=512,worker_time_limit_seconds=300,target_main_seconds=180,protected_hashes=protected,
        sampling='largest-remainder proportional strata: 12h block x tenant x provider/model x cache-used; seeded random rows within strata',
        original_train_window=[original_train.timestamp.min(),original_train.timestamp.max()],sample_train_window=[train.timestamp.min(),train.timestamp.max()],
        original_eval_window=[evaluation.timestamp.min(),evaluation.timestamp.max()],sample_eval_window=[sample.timestamp.min(),sample.timestamp.max()],
        cap_interpretation='8192 is a generous modeled ceiling, not a verified historical provider limit; cap chosen to avoid censoring observed output, estimates fit to training only'))
    print(json.dumps(dict(stage='prepare',training=1250,evaluation=5000,peak_memory_mib=(memory() or 0)/2**20,sanity=reports),default=str),flush=True)


def worker(stage,replicates):
    destination=BASE/stage;destination.mkdir()
    # Windows venv python.exe can be a launcher: monitor/stop the interpreter PID,
    # not just Popen.pid, to enforce limits on the process actually doing work.
    dump(destination/'worker_pid.json',dict(pid=os.getpid()))
    plan=json.loads((BASE/'study_plan.json').read_text())
    train=pd.read_csv(BASE/'training.csv');evaluation=pd.read_csv(BASE/('tiny_evaluation.csv' if stage=='tiny' else 'evaluation.csv'))
    policies=('FCFS','Adaptive','Pacing') if stage in ('tiny','quantile') else POLICIES
    assert len(evaluation)<=8000 and (replicates<=11 if stage=='quantile' else replicates<=50)
    frame=pd.concat([train,evaluation],ignore_index=True)
    config=ExperimentConfig(budget_fractions=(.7,),replicates=replicates,seed=SEED,training_fraction=(len(train)+.25)/len(frame),
        bootstrap_method='local_12h',bootstrap_block_hours=12,bootstrap_window_days=3.,demand_imbalance=(1.,),
        estimator_noise=(0.,),routing_eligibility=(0.,),reservation_multipliers=(1.,),routed_output_multipliers=(1.,),
        policies=policies,trace_replicates=(),trace_policies=(),timeseries_stride=10000,output_cap=8192,model_output_caps=CAPS,
        reservation_mode='quantile' if stage=='quantile' else 'mean',reservation_quantile=.9,
        tenant_roster=tuple(plan['tenants']),horizon_start=HORIZON[0],horizon_end=HORIZON[1],
        data_label='MODELED OCTOBER COMPETITION SUBSET; synthetic telemetry; conditional local-block resampling')
    catalog=load_catalog(ROOT/'results/canonical/configuration/price_catalog_micro_usd.json')
    audits=[];original=SimulationEngine.run;started=time.perf_counter()
    def bounded(self,requests,**kwargs):
        assert len(requests)<=8000
        if time.perf_counter()-started>295:raise TimeoutError('Internal stage deadline')
        if (memory() or 0)>MEMORY_LIMIT:raise MemoryError('Worker memory ceiling')
        content=hashlib.sha256()
        for row in requests:content.update((str(row['request_id'])+'|'+str(row['timestamp'])+'|'+str(row['output_tokens'])+';').encode())
        draws=hashlib.sha256(np.asarray(kwargs['cost_multipliers'],dtype=np.float64).tobytes()).hexdigest()
        events=original(self,requests,**kwargs)
        assert self.ledger.global_spent+self.ledger.global_remaining==self.budget and self.ledger.total_reserved()==0
        assert self.ledger.global_remaining>=0
        audits.append(dict(scenario_id=self.scenario_id,policy=self.policy.label,request_count=len(requests),budget=self.budget,
            workload_hash=content.hexdigest(),draw_hash=draws,delivered_output_tokens=sum(e.allowed_output_tokens for e in events),
            outstanding_reservations=self.ledger.total_reserved()))
        print(json.dumps(dict(completed_policy_runs=len(audits),elapsed_seconds=round(time.perf_counter()-started,2))),flush=True)
        return events
    SimulationEngine.run=bounded
    try:result=ExperimentRunner(catalog,config).run(frame.to_dict('records'))
    finally:SimulationEngine.run=original
    elapsed=time.perf_counter()-started
    runs=result.run_metrics
    assert result.event_traces.empty and len(runs)==replicates*len(policies)
    assert result.scenario_metadata['training_request_count']==len(train)
    assert (runs.completed_original+runs.truncated+runs.rejected==runs.request_count).all()
    assert runs.overrun_micro_usd.eq(0).all() and runs.completed_routed.eq(0).all()
    checks=pd.DataFrame(audits)
    for _,g in checks.groupby('scenario_id'):
        assert g.workload_hash.nunique()==g.draw_hash.nunique()==g.budget.nunique()==1
        assert g.request_count.nunique()==1 and len(g)==len(policies)
    # Cross-replicate IDs differ too; the summary's independent block-choice audit
    # verifies distinct RNG draws without relying on replicate-specific IDs.
    assert checks[checks.policy=='FCFS'].workload_hash.nunique()==replicates
    for name,data in [('run_metrics',runs),('tenant_metrics',result.tenant_metrics),('policy_comparisons',result.policy_comparisons),
        ('experiment_summary',result.experiment_summary),('pairing_audit',checks)]:data.to_csv(destination/f'{name}.csv',index=False)
    result.scenario_metadata['training_window']='fixed chronological pre-evaluation sample; model reservations, tenant quota weights and threshold calibration use training only'
    result.scenario_metadata['evaluation_window']='October 7-30 UTC subset; replay or local 12-hour blocks sampled within +/-3 days and retimed within the fixed horizon'
    dump(destination/'scenario_metadata.json',result.scenario_metadata)
    dump(destination/'runtime.json',dict(stage=stage,replicates=replicates,policy_runs=len(runs),runtime_seconds=elapsed,
        peak_worker_mib=(memory() or 0)/2**20,output_bytes=sum(p.stat().st_size for p in destination.iterdir()),
        request_count_min=int(runs.request_count.min()),request_count_max=int(runs.request_count.max()),completed=True))
    print('COMPLETE '+(destination/'runtime.json').read_text(),flush=True)


def launch(stage,replicates):
    if (BASE/stage).exists():raise SystemExit('Stage exists; refusing overwrite.')
    if stage=='main':
        assert (BASE/'tiny/runtime.json').exists() and (BASE/'pilot/runtime.json').exists()
        diagnostics=json.loads((BASE/'pilot/runtime.json').read_text())
        assert diagnostics['completed'] and diagnostics['peak_worker_mib']<450
        estimate=diagnostics['runtime_seconds']/diagnostics['replicates']*replicates*1.2
        if estimate>180:raise SystemExit(f'Projected {estimate:.1f}s exceeds planning target; reduce replicates (>=31).')
        assert 31<=replicates<=50
    if stage=='quantile':
        assert json.loads((BASE/'main/runtime.json').read_text())['runtime_seconds']<180
        assert replicates<=11
    if stage in ('tiny','pilot'):assert replicates==3
    log=BASE/f'{stage}.log';began=time.perf_counter();observed_peak=0
    with log.open('w',encoding='utf-8') as output:
        process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'worker','--stage',stage,'--replicates',str(replicates)],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
        while process.poll() is None:
            pid_path=BASE/stage/'worker_pid.json'
            actual_pid=json.loads(pid_path.read_text())['pid'] if pid_path.exists() else process.pid
            observed_peak=max(observed_peak,memory(actual_pid) or 0)
            if time.perf_counter()-began>300 or observed_peak>MEMORY_LIMIT:
                if actual_pid!=process.pid:
                    try:os.kill(actual_pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                process.kill();process.wait()
                dump(BASE/f'{stage}_stopped.json',dict(elapsed=time.perf_counter()-began,peak_mib=observed_peak/2**20,limit='300 seconds / 512 MiB'))
                raise SystemExit('Worker stopped at hard resource limit; incomplete outputs are not results.')
            time.sleep(.2)
    if process.returncode:raise SystemExit(f'Worker failed: see {log}')
    diagnostics=json.loads((BASE/stage/'runtime.json').read_text())
    diagnostics.update(parent_wall_seconds=time.perf_counter()-began,parent_observed_peak_worker_mib=observed_peak/2**20)
    dump(BASE/stage/'runtime.json',diagnostics)
    print(json.dumps(diagnostics,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','worker'))
    parser.add_argument('--stage',choices=('tiny','pilot','main','quantile'),default='tiny')
    parser.add_argument('--replicates',type=int,default=3)
    args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='worker':worker(args.stage,args.replicates)
    else:launch(args.stage,args.replicates)
