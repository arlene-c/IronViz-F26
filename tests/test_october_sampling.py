"""Tiny sampling tests only; never execute the October study."""
from datetime import datetime, timedelta, timezone

import pandas as pd

from tools.run_october_monte_carlo import stratified


def source():
    start=datetime(2026,10,7,tzinfo=timezone.utc)
    rows=[]
    for block in range(4):
        for tenant in range(3):
            for cache in range(2):
                for i in range(10):
                    rows.append(dict(request_id=f'{block}-{tenant}-{cache}-{i}',
                        timestamp=(start+timedelta(hours=12*block,minutes=20*tenant+10*cache+i)).isoformat(),
                        tenant=f't{tenant}',provider='synthetic',model='m',cached_input_tokens=cache,
                        input_tokens=10+i,output_tokens=5+i))
    return pd.DataFrame(rows)


def test_october_strata_preserve_proportions_and_chronology():
    frame=source();sample=stratified(frame,48,0)
    assert len(sample)==48 and sample.request_id.is_unique
    assert sample.timestamp.is_monotonic_increasing
    assert sample.groupby('tenant').size().eq(16).all()
    assert sample.groupby(['tenant','cached_input_tokens']).size().eq(8).all()
    assert pd.to_datetime(sample.timestamp,utc=True).dt.floor('12h').value_counts().eq(12).all()
    pd.testing.assert_frame_equal(sample,stratified(frame,48,0))
    assert sample.request_id.tolist()!=stratified(frame,48,1).request_id.tolist()


def test_october_sampling_retains_source_values_without_replacement():
    frame=source();sample=stratified(frame,48,0)
    original=frame.set_index('request_id').loc[sample.request_id].reset_index()
    pd.testing.assert_frame_equal(sample,original)
