"""The descriptive preparation entry point must never run legacy experiments by default."""
import sys

import pandas as pd

from src import ironviz_experiments as preparation


def test_default_preparation_stops_before_any_policy_execution(tmp_path,monkeypatch):
    frame=pd.DataFrame([dict(request_id='synthetic-only',timestamp=pd.Timestamp('2026-10-01',tz='UTC'),
        provider='OpenAI',tenant='test',model='gpt-4o',status=200,success=True,
        input_tokens=10,cached_tokens=0,output_tokens=5,exclude_reason='',error='')])
    prices=pd.DataFrame([dict(model='gpt-4o',input_per_million=2.5,cached_input_per_million=1.25,
        output_per_million=10.,cheaper_model='')]).set_index('model')
    monkeypatch.setattr(preparation,'clean_telemetry',lambda *args:frame)
    monkeypatch.setattr(preparation,'read_prices',lambda *args:prices)
    written=[]
    monkeypatch.setattr(preparation,'write_analysis',lambda *args:written.append(True))
    def forbidden(*args,**kwargs):raise AssertionError('Preparation executed a policy')
    monkeypatch.setattr(preparation,'run',forbidden)
    monkeypatch.setattr(preparation,'simulate',forbidden)
    monkeypatch.setattr(sys,'argv',['prepare','--openai','unused','--gemini','unused','--prices','unused','--out',str(tmp_path)])
    preparation.main()
    assert written==[True]
    assert (tmp_path/'clean_requests.csv').exists() and (tmp_path/'requests_sim.csv').exists()
    assert not (tmp_path/'results.csv').exists()
