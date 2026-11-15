"""Read saved pilot aggregates and run one 50-row controlled cap comparison.

Never invokes the Monte Carlo pilot, bootstrap, legacy pipeline, or full data.
Six 40-event policy runs = 240 admission decisions; no figures are generated.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from ironviz_f26.experiments import ExperimentConfig, ExperimentRunner
from ironviz_f26.policies import Pacing
from ironviz_f26.pricing import PriceCatalog, PriceRecord


def main():
    root=Path(__file__).resolve().parents[1]
    destination=root/'outputs/pacing_investigation'
    if destination.exists():
        raise SystemExit('Investigation directory exists; refusing to overwrite or rerun.')
    pilot=root/'outputs/monte_carlo_pilot'
    pilot_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in pilot.iterdir() if p.is_file()}
    runs=pd.read_csv(pilot/'run_metrics.csv')
    outcome_columns=['completed_original','truncated','rejected','admitted','budget_utilization',
        'token_weighted_served_share','cost_weighted_served_share','completion_size_q1','completion_size_q2',
        'completion_size_q3','completion_size_q4','output_cap_exceeded_count','reservation_shortfall_count']
    replay=runs[runs.replicate==0][['policy',*outcome_columns]].copy()
    medians=runs[runs.replicate>0].groupby('policy')[outcome_columns].median().reset_index()

    seed=20261114
    rng=np.random.default_rng(seed)
    # Fixed training mean=30; evaluation has independently shuffled size/output
    # tiers. No temporal cost trend or policy-specific requests are introduced.
    inputs=rng.permutation([100]*30+[900]*10)
    outputs=rng.permutation([10,20,30,60]*10)
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    rows=[]
    for i in range(50):
        output=[10,20,60,10,20,60,10,20,60,30][i] if i<10 else int(outputs[i-10])
        rows.append(dict(request_id=f'control-{i:02d}',timestamp=(start+timedelta(minutes=i)).isoformat(),
            tenant=('a','b','c')[i%3],provider='synthetic',model='one',input_tokens=100 if i<10 else int(inputs[i-10]),
            cached_input_tokens=0,output_tokens=output,original_status='success'))
    assert len(rows)==50 and sum(r['output_tokens'] for r in rows[:10])/10==30
    catalog=PriceCatalog('SYNTHETIC CONTROL ONLY', {('synthetic','one'):PriceRecord('synthetic','one',1_000_000,0,1_000_000)})
    summaries=[]; group_rows=[]; traces=[]; audits=[]
    original_decide=Pacing.decide
    active_cap=None
    def checked_decide(self,view,state):
        timestamp=datetime.fromisoformat(view.timestamp.replace('Z','+00:00')).timestamp()
        begin=(start+timedelta(minutes=10)).timestamp()
        end=(start+timedelta(minutes=50)).timestamp()
        progress=max(0.,min(1.,(timestamp-begin)/(end-begin)))
        spent=self.budget-state.global_remaining
        allowance=self.budget*min(1.,progress+.05)
        expected=view.estimated_cost<=state.global_remaining and spent+view.estimated_cost<=allowance
        actual=original_decide(self,view,state)
        assert actual==expected
        audits.append(dict(cap=active_cap,request_id=view.request_id,timestamp=view.timestamp,
            input_tokens=view.input_tokens,reservation=view.estimated_cost,spent_before=spent,
            remaining_before=state.global_remaining,allowance=allowance,pace_credit=allowance-spent,
            expected_admit=expected,actual_admit=actual))
        return actual
    started=time.perf_counter()
    Pacing.decide=checked_decide
    try:
        for cap in (16,1024):
            active_cap=cap
            config=ExperimentConfig(budget_fractions=(.7,),replicates=1,bootstrap=False,training_fraction=.2,
                demand_imbalance=(1.,),estimator_noise=(0.,),routing_eligibility=(0.,),routed_output_multipliers=(1.,),
                policies=('FCFS','Adaptive','Pacing'),trace_replicates=(0,),seed=seed,output_cap=cap,
                tenant_roster=('a','b','c'),horizon_start=(start+timedelta(minutes=10)).isoformat(),
                horizon_end=(start+timedelta(minutes=50)).isoformat(),data_label='EXPLORATORY SYNTHETIC CAP CONTROL')
            result=ExperimentRunner(catalog,config).run(rows)
            joined=result.event_traces.merge(pd.DataFrame(rows)[['request_id','input_tokens','output_tokens']],on='request_id',validate='many_to_one')
            joined['cap']=cap
            joined['input_tier']=np.where(joined.input_tokens==100,'100 tokens','900 tokens')
            traces.append(joined)
            for policy,events in joined.groupby('policy'):
                metrics=result.run_metrics[result.run_metrics.policy==policy].iloc[0]
                delivered=int(events.allowed_output_tokens.sum())
                summaries.append(dict(cap=cap,policy=policy,requests=len(events),completed=int(metrics.completed_original),
                    truncated=int(metrics.truncated),rejected=int(metrics.rejected),admitted=int(metrics.admitted),
                    completion_rate=float(metrics.completion_rate_original),delivered_output_tokens=delivered,
                    demanded_output_tokens=int(events.output_tokens.sum()),output_token_share=delivered/events.output_tokens.sum(),
                    delivered_input_tokens=int(events.loc[events.decision=='ADMITTED','input_tokens'].sum()),
                    budget_micro_usd=int(metrics.budget_micro_usd),spend_micro_usd=int(metrics.realized_cost_micro_usd),
                    budget_utilization=float(metrics.budget_utilization),cap_exceeded=int(metrics.output_cap_exceeded_count),
                    reservation_shortfall=int(metrics.reservation_shortfall_count)))
                assert len(events)==40 and events.request_id.is_unique
                assert int(metrics.completed_original+metrics.truncated+metrics.rejected)==40
                for tier,g in events.groupby('input_tier'):
                    group_rows.append(dict(cap=cap,policy=policy,input_tier=tier,requests=len(g),
                        completed=int(g.outcome.eq('COMPLETED_ORIGINAL').sum()),truncated=int(g.outcome.eq('TRUNCATED_ORIGINAL').sum()),
                        rejected=int(g.outcome.eq('REJECTED').sum()),completion_rate=g.outcome.eq('COMPLETED_ORIGINAL').mean(),
                        delivered_output_tokens=int(g.allowed_output_tokens.sum())))
    finally:
        Pacing.decide=original_decide
    runtime=time.perf_counter()-started
    assert len(audits)==80 and sum(r['requests'] for r in summaries)==240
    assert {r['budget_micro_usd'] for r in summaries}=={summaries[0]['budget_micro_usd']}
    for name,expected in pilot_hashes.items():
        assert hashlib.sha256((pilot/name).read_bytes()).hexdigest()==expected,name
    destination.mkdir(parents=True)
    for name,frame in [('pilot_replay_outcomes',replay),('pilot_resample_medians',medians),
        ('controlled_outcomes',pd.DataFrame(summaries)),('controlled_size_groups',pd.DataFrame(group_rows)),
        ('controlled_events',pd.concat(traces,ignore_index=True)),('pacing_rule_audit',pd.DataFrame(audits)),
        ('controlled_requests',pd.DataFrame(rows))]:
        frame.to_csv(destination/f'{name}.csv',index=False)
    metadata=dict(label='EXPLORATORY SYNTHETIC; not October evidence',seed=seed,source_requests=50,training_requests=10,
        evaluation_requests=40,policy_runs=6,total_admission_decisions=240,caps=[16,1024],bootstrap=False,
        training_mean_output=30,matched_budget=True,pacing_rule_checks=80,pacing_rule_mismatches=0,
        runtime_seconds=runtime,pilot_output_hashes=pilot_hashes,
        limitations='Original pilot did not retain delivered output totals or event traces; they cannot be reconstructed from aggregate token-weighted input+output shares alone.')
    (destination/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    print(pd.DataFrame(summaries).to_string(index=False))
    print(pd.DataFrame(group_rows).to_string(index=False))
    print(json.dumps(dict(runtime_seconds=runtime,decisions=240,pacing_rule_checks=80,mismatches=0)))


if __name__=='__main__':
    main()
