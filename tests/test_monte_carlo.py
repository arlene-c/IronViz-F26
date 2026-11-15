"""Bounded stochastic validation: <=36 input rows, <=3 replicates per runner call."""
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from ironviz_f26.engine import SimulationEngine
from ironviz_f26.estimators import GlobalEstimator
from ironviz_f26.experiments import ExperimentConfig, ExperimentRunner, day_block_bootstrap, local_block_bootstrap, _metrics, _paired_comparisons
from ironviz_f26.policies import AdaptiveSharing, CostThreshold, FCFS, Pacing
from ironviz_f26.pricing import PriceCatalog, PriceRecord
from ironviz_f26.routing import RoutingWrapper


def workload():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [dict(request_id=f'd{day}b{block}r{i}', timestamp=(start + timedelta(days=day, hours=12*block, minutes=i)).isoformat(),
                 tenant=('a','b','c')[i], provider='p', model='m', input_tokens=1, cached_input_tokens=0,
                 output_tokens=2 + day + block + i, original_status='success')
            for day in range(6) for block in range(2) for i in range(3)]


def catalog():
    return PriceCatalog('SYNTHETIC', {('p','m'): PriceRecord('p','m', 1_000_000, 0, 1_000_000)})


def config(**kwargs):
    values = dict(budget_fractions=(.7,), replicates=3, seed=812, training_fraction=.25,
                  bootstrap_method='local_12h', bootstrap_window_days=1., demand_imbalance=(1.,),
                  estimator_noise=(.25,), routing_eligibility=(0.,), routed_output_multipliers=(1.,),
                  policies=('FCFS','Adaptive','Pacing'), trace_replicates=(0,1,2), timeseries_stride=10,
                  tenant_roster=('a','b','c'), horizon_start='2026-01-01T00:00:00Z', horizon_end='2026-01-08T00:00:00Z')
    values.update(kwargs)
    return ExperimentConfig(**values)


@pytest.mark.parametrize('sampler', [day_block_bootstrap, local_block_bootstrap])
def test_sampler_reproducibility_and_distinct_draws(sampler):
    rows = workload()
    a = sampler(rows, seed=812, replicate=1)
    assert a == sampler(rows, seed=812, replicate=1)
    # Ignore resampled request IDs, which encode replicate even for identical draws.
    signature = lambda sample: [(r['source_request_id'], r['timestamp']) for r in sample]
    assert signature(a) != signature(sampler(rows, seed=812, replicate=2))
    assert signature(a) != signature(sampler(rows, seed=813, replicate=1))


def test_whole_days_preserve_every_record_and_offset():
    source = workload(); by_id = {r['request_id']:r for r in source}
    sample = day_block_bootstrap(source, seed=812, replicate=1)
    groups = defaultdict(list)
    for row in sample:
        groups[row['timestamp'][:10]].append(row)
    for records in groups.values():
        originals = [by_id[r['source_request_id']] for r in records]
        day = originals[0]['timestamp'][:10]
        assert {r['request_id'] for r in originals} == {r['request_id'] for r in source if r['timestamp'][:10] == day}
        for copied, original in zip(records, originals):
            assert datetime.fromisoformat(copied['timestamp'].replace('Z','+00:00')).time() == datetime.fromisoformat(original['timestamp']).time()
            assert copied['output_tokens'] == original['output_tokens']


def test_local_blocks_keep_structure_and_calendar_window():
    source = workload(); by_id = {r['request_id']:r for r in source}
    sample = local_block_bootstrap(source, seed=812, replicate=1, window_days=1.)
    groups = defaultdict(list)
    start = datetime(2026,1,1,tzinfo=timezone.utc)
    for copied in sample:
        timestamp = datetime.fromisoformat(copied['timestamp'].replace('Z','+00:00'))
        target_block = int((timestamp-start).total_seconds() // 43200)
        groups[target_block].append(copied)
    for target, records in groups.items():
        originals = [by_id[r['source_request_id']] for r in records]
        original_time = datetime.fromisoformat(originals[0]['timestamp'])
        block = int((original_time-start).total_seconds() // 43200)
        assert abs(target-block) <= 2
        assert {r['request_id'] for r in originals} == {r['request_id'] for r in source if int((datetime.fromisoformat(r['timestamp'])-start).total_seconds()//43200)==block}
        for copied, original in zip(records, originals):
            a=datetime.fromisoformat(copied['timestamp'].replace('Z','+00:00'))
            b=datetime.fromisoformat(original['timestamp'])
            assert (a-start).total_seconds()%43200 == (b-start).total_seconds()%43200


def test_policies_share_workload_and_cost_stream_independent_of_order(monkeypatch):
    observed = defaultdict(list); actual = SimulationEngine.run
    def capture(self, rows, **kwargs):
        observed[(self.scenario_id, self.policy.label)].append((
            tuple((r['request_id'],r['timestamp'],r['output_tokens']) for r in rows),
            tuple(kwargs['cost_multipliers']), dict(kwargs['estimated_costs'])))
        return actual(self, rows, **kwargs)
    monkeypatch.setattr(SimulationEngine, 'run', capture)
    first = ExperimentRunner(catalog(), config()).run(workload())
    for scenario in first.run_metrics.scenario_id.unique():
        values=[observed[(scenario,p)][0] for p in config().policies]
        assert values[0] == values[1] == values[2]
    second = ExperimentRunner(catalog(), config(policies=('Pacing','Adaptive','FCFS'))).run(workload())
    for values in observed.values():
        assert len(values)==2 and values[0]==values[1]
    columns=['scenario_id','policy','completed_original','realized_cost_micro_usd']
    pd.testing.assert_frame_equal(first.run_metrics[columns].sort_values(columns[:2]).reset_index(drop=True),
                                  second.run_metrics[columns].sort_values(columns[:2]).reset_index(drop=True))


def test_estimates_do_not_use_evaluation_outputs():
    rows=workload(); changed=[dict(r) for r in rows]
    for r in changed[9:]: r['output_tokens'] *= 100
    cfg=config(policies=('FCFS',),replicates=1)
    a=ExperimentRunner(catalog(),cfg).run(rows).event_traces
    b=ExperimentRunner(catalog(),cfg).run(changed).event_traces
    assert a[['request_id','estimated_cost']].equals(b[['request_id','estimated_cost']])
    # Budgets are retrospective fractions of reference cost, so decisions need not match here.


@pytest.mark.parametrize('replicates',[1,2,3])
def test_replay_and_resamples_separate_and_small_samples_have_no_intervals(replicates):
    result=ExperimentRunner(catalog(),config(policies=('FCFS','Pacing'),replicates=replicates)).run(workload())
    summary=result.experiment_summary
    assert summary[summary.workload_kind=='replay'].replicates.eq(1).all()
    if replicates>1:
        assert summary[summary.workload_kind=='local_12h_block_bootstrap'].replicates.eq(replicates-1).all()
    assert summary.filter(regex='^ci95_').isna().all().all()
    paired=result.policy_comparisons
    baseline=result.run_metrics[result.run_metrics.policy=='FCFS'].set_index(['scenario_id','replicate'])
    for r in paired.itertuples():
        fcfs=baseline.loc[(r.scenario_id,r.replicate)]
        assert r.fcfs_completed_original==fcfs.completed_original
        assert r.paired_completed_original_difference==r.completed_original-fcfs.completed_original
    shuffled=_paired_comparisons(result.run_metrics.sample(frac=1,random_state=9))
    cols=['scenario_id','replicate','policy','paired_completed_original_difference']
    pd.testing.assert_frame_equal(paired[cols].sort_values(cols[:3]).reset_index(drop=True),shuffled[cols].sort_values(cols[:3]).reset_index(drop=True))


def test_provider_qualified_training_and_routed_reservations():
    cat=PriceCatalog('SYNTHETIC', {('p','shared'):PriceRecord('p','shared',0,0,2_000_000),
                                  ('q','shared'):PriceRecord('q','shared',0,0,1_000_000)})
    rows=[dict(workload()[i],request_id=f'r{i}',provider=p,model='shared',input_tokens=0,output_tokens=y)
          for i,(p,y) in enumerate([('p',10),('q',30),('p',10),('q',30)])]
    result=ExperimentRunner(cat,config(training_fraction=.5,replicates=1,policies=('FCFS',),estimator_noise=(0.,))).run(rows)
    assert result.event_traces.estimated_cost.tolist()==[20,30]
    routed=ExperimentRunner(cat,config(training_fraction=.5,replicates=1,policies=('FCFS','FCFS+Routing'),estimator_noise=(0.,),
        routing_eligibility=(1.,),routed_output_multipliers=(.5,),routing_compatibility=(('p','shared','q','shared'),))).run(rows)
    assert routed.event_traces[routed.event_traces.policy=='FCFS'].estimated_cost.tolist()==[20,30]
    assert routed.event_traces[routed.event_traces.policy=='FCFS+Routing'].estimated_cost.tolist()==[5,30]
    engine=SimulationEngine(cat,FCFS(),100,GlobalEstimator([0]))
    with pytest.raises(ValueError,match='ambiguous'):
        engine.run([rows[2]],estimated_costs={('r2','shared'):20})


def test_threshold_candidates_match_strict_engine_and_allow_reject_all():
    cat=catalog(); rows=workload()[:6]
    reservations=[4,9,3,9,5,8]
    estimates={(r['request_id'],'p','m'):v for r,v in zip(rows,reservations)}
    # Generous replay gets per-admission settlement and completion at each reservation.
    events=SimulationEngine(cat,FCFS(),1000,GlobalEstimator([0])).run(rows,estimated_costs=estimates)
    fitted=CostThreshold().fit(reservations,14,settlement_costs=[e.realized_cost for e in events],
                               completion_flags=[e.outcome=='COMPLETED_ORIGINAL' for e in events])
    scores={}
    for tau in fitted.tuning_candidates:
        engine=SimulationEngine(cat,CostThreshold(tau),14,GlobalEstimator([0]))
        replay=engine.run(rows,estimated_costs=estimates)
        scores[tau]=(sum(e.outcome=='COMPLETED_ORIGINAL' for e in replay),-sum(e.realized_cost for e in replay),-tau)
    assert fitted.tau==max(scores,key=scores.get)
    assert CostThreshold().fit([4,5],20,settlement_costs=[3,4],completion_flags=[False,False]).tau==0


@pytest.mark.parametrize('mode',['mean','quantile','cap'])
def test_runner_training_vectors_reconcile_with_engine(monkeypatch, mode):
    captured={}; actual=CostThreshold.fit
    def capture(self, reservations, budget, **kwargs):
        captured.update(reservations=list(reservations), budget=budget, **kwargs)
        return actual(self,reservations,budget,**kwargs)
    monkeypatch.setattr(CostThreshold,'fit',capture)
    cfg=config(policies=('Threshold',),replicates=1,reservation_mode=mode,output_cap=6)
    ExperimentRunner(catalog(),cfg).run(workload())
    training=workload()[:9]
    estimates={(r['request_id'],'p','m'):v for r,v in zip(training,captured['reservations'])}
    events=SimulationEngine(catalog(),FCFS(),1000,GlobalEstimator([0]),output_cap=6).run(training,estimated_costs=estimates)
    assert captured['settlement_costs']==[e.realized_cost for e in events]
    assert captured['completion_flags']==[e.outcome=='COMPLETED_ORIGINAL' for e in events]


@pytest.mark.parametrize('factory',[AdaptiveSharing,Pacing])
def test_timed_policy_prefix_survives_future_request_changes(factory):
    rows=workload(); prefix=rows[:12]
    changed=[dict(r,output_tokens=r['output_tokens']*100,tenant='new') for r in rows[12:]]
    def run(requests):
        return SimulationEngine(catalog(),factory(),100,GlobalEstimator([7]),tenant_roster=('a','b','c'),
            horizon_start='2026-01-01T00:00:00Z',horizon_end='2026-01-08T00:00:00Z').run(requests)
    assert run(rows)[:12]==run(prefix+changed)[:12]


def test_cost_per_completion_includes_wasted_spending_and_zero_denominators():
    rows=[dict(workload()[i],output_tokens=y) for i,y in enumerate([2,20])]
    events=SimulationEngine(catalog(),FCFS(),100,GlobalEstimator([5])).run(rows)
    metrics,_=_metrics(events,rows,catalog(),budget=100,reference_cost=24)
    assert metrics['completed_original']==1 and metrics['truncated']==1
    assert metrics['cost_per_completed_request_micro_usd']==8  # 3 completed spend + 5 truncated spend.
    assert metrics['cost_per_original_completion_micro_usd']==8
    assert metrics['cost_per_routed_completion_micro_usd'] is None
