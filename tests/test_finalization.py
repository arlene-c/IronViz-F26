"""Small regression checks only; never load raw data or execute full-data jobs."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from ironviz_f26.adapter import InputAdapter
from ironviz_f26.cli import load_catalog
from ironviz_f26.engine import SimulationEngine
from ironviz_f26.estimators import GlobalEstimator
from ironviz_f26.experiments import ExperimentConfig, ExperimentRunner, _metrics
from ironviz_f26.ledger import Ledger
from ironviz_f26.money import Money
from ironviz_f26.policies import FCFS, Quotas, Pacing, AdaptiveSharing, CostThreshold
from ironviz_f26.pricing import PriceCatalog, PriceRecord

ROOT = Path(__file__).resolve().parents[1]


def test_curated_results_are_unchanged_and_reconcile():
    manifest = json.loads((ROOT / 'results/canonical/manifest.json').read_text())
    assert manifest['status'].startswith('PRE-CORRECTION')
    for entry in manifest['files']:
        path = ROOT / entry['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        assert path.stat().st_size < 2_000_000
    runs = pd.read_csv(ROOT / 'results/canonical/policies/run_metrics.csv')
    tenants = pd.read_csv(ROOT / 'results/canonical/policies/tenant_metrics.csv')
    assert len(runs) == 24 and len(tenants) == 144
    assert runs.run_id.is_unique
    assert (runs.completed_original + runs.rejected + runs.truncated == runs.request_count).all()
    assert (runs.realized_cost_micro_usd + runs.budget_remaining_micro_usd == runs.budget_micro_usd).all()
    assert tenants.groupby('run_id').completed_original.sum().sort_index().equals(
        runs.set_index('run_id').completed_original.sort_index())
    expected = dict(FCFS=42573, Quotas=36641, TrainingQuotas=44699, Adaptive=45768, Pacing=46217, Threshold=47384)
    assert runs[runs.budget_fraction == .7].set_index('policy').completed_original.to_dict() == expected


def row(identifier='r0', output=10, timestamp='2026-01-01T00:00:00Z', tenant='a', model='high'):
    return dict(request_id=identifier, timestamp=timestamp, provider='test', model=model,
                tenant=tenant, input_tokens=0, cached_input_tokens=0, output_tokens=output, original_status='success')


def catalog():
    return PriceCatalog('test', {('test', 'high'): PriceRecord('test', 'high', 0, 0, 2_000_000),
                                 ('test', 'low'): PriceRecord('test', 'low', 0, 0, 1_000_000)})


def test_integer_money_beyond_float_precision():
    assert Money.cost_for_tokens(2**60 + 1, 1_000_000) == 2**60 + 1
    with pytest.raises(ValueError):
        Money.cost_for_tokens(1, 1.2)


def test_aggregate_ledger_releases_all_reservation():
    ledger = Ledger(100)
    ledger.reserve('a', 50)
    ledger.settle('a', 10)
    assert ledger.total_reserved() == 0
    assert ledger.global_remaining + ledger.global_spent == 100
    with pytest.raises(ValueError):
        ledger.settle('a', 1)


@pytest.mark.parametrize('price', [-1, 1.5, True, float('nan')])
def test_invalid_prices_rejected(price):
    with pytest.raises(ValueError):
        PriceRecord('test', 'high', price, 0, 1)


def test_duplicate_catalog_and_units_rejected(tmp_path):
    path = tmp_path / 'catalog.json'
    record = dict(provider='test', model='high', input_price=1, cached_input_price=0, output_price=2)
    payload = dict(version='test', price_unit='integer micro-USD per 1M tokens', rows=[record, record])
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='duplicate'):
        load_catalog(path)
    payload['rows'] = [record]; payload['price_unit'] = 'USD'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='price_unit'):
        load_catalog(path)
    with pytest.raises(ValueError, match='keys'):
        PriceCatalog('test', {('wrong', 'high'): PriceRecord('test', 'high', 1, 0, 2)})


def test_utc_adapter_and_engine_sort_mixed_offsets():
    rows = [row('early', timestamp='2026-01-01T01:00:00+02:00'), row('late', timestamp='2026-01-01T00:00:00Z')]
    normalized, errors = InputAdapter()._coerce_dataframe(pd.DataFrame(rows))
    assert not errors and normalized[0].timestamp == '2025-12-31T23:00:00.000000Z'
    events = SimulationEngine(catalog(), FCFS(), 100, GlobalEstimator([20])).run(list(reversed(rows)))
    assert [event.request_id for event in events] == ['early', 'late']


@pytest.mark.parametrize('policy', [Quotas, AdaptiveSharing, Pacing])
def test_explicit_roster_horizon_preserve_prefix(policy):
    def run(suffix):
        engine = SimulationEngine(catalog(), policy(), 100, GlobalEstimator([20]), tenant_roster=('a', 'b'),
                                  horizon_start='2026-01-01T00:00:00Z', horizon_end='2026-01-02T00:00:00Z')
        return engine.run([row('first', timestamp='2026-01-01T12:00:00Z'), suffix])[0]
    first = run(row('next', timestamp='2026-01-01T13:00:00Z', tenant='b'))
    changed = run(row('future', output=1000, timestamp='2026-01-01T23:00:00Z', tenant='new'))
    assert first == changed


def test_trace_separates_cap_reservation_and_denial():
    engine = SimulationEngine(catalog(), FCFS(), 100, GlobalEstimator([10]), output_cap=8)
    event = engine.run([row(output=7)])[0]
    assert event.reservation_shortfall and not event.output_cap_exceeded
    assert event.outcome == 'TRUNCATED_ORIGINAL'
    event = SimulationEngine(catalog(), FCFS(), 100, GlobalEstimator([30]), output_cap=8).run([row(output=10)])[0]
    assert event.output_cap_exceeded and not event.reservation_shortfall
    rejected = SimulationEngine(catalog(), FCFS(), 1, GlobalEstimator([30])).run([row()])[0]
    assert rejected.denial_reason == 'GLOBAL_BUDGET'
    assert rejected.tenant_remaining is None


def test_quota_trace_reports_actual_entitlement():
    event = SimulationEngine(catalog(), Quotas(), 100, GlobalEstimator([20]), tenant_roster=('a', 'b')).run([row(output=5)])[0]
    assert event.tenant_remaining == 40  # 50 allocation minus 10 actual spend.


def test_selected_target_cap_and_training_only_estimates():
    rows = [row(f'r{i}', output=y, timestamp=f'2026-01-01T00:00:0{i}Z') for i, y in enumerate([10, 30, 80, 100])]
    config = ExperimentConfig(budget_fractions=(1.,), replicates=1, bootstrap=False, training_fraction=.5,
        demand_imbalance=(1.,), routing_eligibility=(1.,), routed_output_multipliers=(.7,),
        policies=('FCFS+Routing',), reservation_mode='cap', model_output_caps={'high':40, 'low':100},
        routing_compatibility=(('test','high','test','low'),))
    result = ExperimentRunner(catalog(), config).run(rows)
    assert result.event_traces.estimated_cost.tolist() == [100, 100]
    assert result.event_traces.selected_model.eq('low').all()
    assert result.run_metrics.gap_to_max_min_rate_hindsight.isna().all()
    assert result.experiment_summary.ci95_low_completed_original.isna().all()


def test_metrics_weight_completions_and_distinguish_first_denial():
    rows = [row('r0', output=5), row('r1', output=10, timestamp='2026-01-01T00:00:01Z')]
    events = SimulationEngine(catalog(), FCFS(), 25, GlobalEstimator([20])).run(rows)
    metrics, tenants = _metrics(events, rows, catalog(), budget=25, reference_cost=30)
    assert metrics['cost_weighted_served_share'] == pytest.approx(10/30)
    assert metrics['first_denial_timestamp'] == '2026-01-01T00:00:01.000000Z'
    assert metrics['time_to_budget_exhaustion_seconds'] is None
    assert tenants[0]['cost_weighted_served_share'] == pytest.approx(10/30)


def test_threshold_calibration_uses_settlement_and_completions():
    threshold = CostThreshold().fit([10,20,20], 25, settlement_costs=[1,1,1], completion_flags=[False,True,True])
    assert threshold.tau == 20


def test_runner_requires_declared_horizon_for_timed_policy():
    config = ExperimentConfig(policies=('Pacing',))
    with pytest.raises(ValueError, match='explicit horizon'):
        ExperimentRunner(catalog(), config).run([row('r0'), row('r1', timestamp='2026-01-01T00:00:01Z')])


def test_summary_spending_win_direction_and_replay_separation():
    from ironviz_f26.experiments import _summarize
    from ironviz_f26.outputs import SUMMARY_METRICS, PAIRED_SUMMARY_METRICS
    key = dict(policy='Threshold', budget_fraction=.7, demand_imbalance=1., estimator_noise_sigma=0.,
               routing_eligibility=0., reservation_multiplier=1., reservation_mode='mean',
               reservation_quantile=.9, output_cap=1024, model_output_caps='{}', routed_output_length_multiplier=.7)
    rows, pairs = [], []
    for kind, count in [('replay', 1), ('day_block_bootstrap', 20)]:
        for i in range(count):
            rows.append(dict(key, workload_kind=kind, **{m:1 for m in SUMMARY_METRICS}))
            pair = dict(key, workload_kind=kind, **{m:2 for m in PAIRED_SUMMARY_METRICS})
            pair['paired_realized_cost_micro_usd_difference'] = -10
            pairs.append(pair)
    summary = _summarize(pd.DataFrame(rows), pd.DataFrame(pairs)).set_index('workload_kind')
    assert len(summary) == 2
    assert pd.isna(summary.loc['replay', 'ci95_low_completed_original'])
    assert summary.loc['day_block_bootstrap', 'win_rate_paired_realized_cost_micro_usd_difference'] == 1


def test_single_policy_smoke_writes_versioned_contract(tmp_path):
    from ironviz_f26.outputs import write_outputs, TRACE_COLUMNS
    rows = [row(f'r{i}', output=y, timestamp=f'2026-01-01T00:00:0{i}Z') for i, y in enumerate([10,30,40,50])]
    config = ExperimentConfig(budget_fractions=(.7,), replicates=1, bootstrap=False,
        demand_imbalance=(1.,), routing_eligibility=(0.,), policies=('Threshold',), training_fraction=.5)
    result = ExperimentRunner(catalog(), config).run(rows)
    write_outputs(result, tmp_path)
    assert result.scenario_metadata['schema_version'].startswith('2')
    assert result.run_metrics.threshold_tau_micro_usd.notna().all()
    assert pd.read_parquet(tmp_path / 'event_traces.parquet').columns.tolist() == TRACE_COLUMNS
    assert 'first_denial_timestamp' in pd.read_csv(tmp_path / 'run_metrics.csv')
