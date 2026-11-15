from __future__ import annotations

import pandas as pd
import pytest

from ironviz_f26.money import Money
from ironviz_f26.pricing import PriceCatalog, PriceRecord
from ironviz_f26.estimators import GlobalEstimator, ModelConditionalEstimator, QuantileEstimator
from ironviz_f26.ledger import Ledger
from ironviz_f26.adapter import InputAdapter, RequestRow


def test_money_rounds_up_to_micro_usd() -> None:
    assert Money.cost_for_tokens(tokens=1_000_000, price_per_million=250) == 250
    assert Money.cost_for_tokens(tokens=1_000_001, price_per_million=250) == 251
    assert Money.cost_for_tokens(tokens=1_000_001, price_per_million=1_000) == 1001


def test_pricing_catalog_version_and_lookup() -> None:
    catalog = PriceCatalog(
        version="v2026-11-01",
        rows={
            ("openai", "gpt-4o"): PriceRecord(provider="openai", model="gpt-4o", input_price=100, cached_input_price=40, output_price=250),
            ("anthropic", "claude-3.5-sonnet"): PriceRecord(provider="anthropic", model="claude-3.5-sonnet", input_price=80, cached_input_price=30, output_price=220),
        },
    )

    assert catalog.version == "v2026-11-01"
    assert catalog.lookup("openai", "gpt-4o").output_price == 250
    assert catalog.lookup("anthropic", "claude-3.5-sonnet").input_price == 80
    with pytest.raises(KeyError):
        catalog.lookup("openai", "missing-model")


def test_estimators_compute_expected_values() -> None:
    costs = [100, 200, 300]
    global_estimator = GlobalEstimator(costs)
    assert global_estimator.estimate() == 200

    model_estimator = ModelConditionalEstimator({"gpt-4o": [100, 200], "gpt-4o-mini": [50, 75]})
    assert model_estimator.estimate("gpt-4o") == 150
    assert model_estimator.estimate("gpt-4o-mini") == 62

    quantile_estimator = QuantileEstimator([100, 200, 300], q=0.75)
    assert quantile_estimator.estimate() == 250


def test_ledger_reconciles_budget_and_settlement() -> None:
    ledger = Ledger(budget=1_000)
    ledger.reserve("tenant-a", 300)
    ledger.reserve("tenant-a", 200)
    ledger.reserve("tenant-b", 250)
    assert ledger.global_remaining == 250
    assert ledger.tenant_remaining("tenant-a") == 500

    ledger.settle("tenant-a", 100)
    assert ledger.global_remaining == 350
    assert ledger.tenant_spent("tenant-a") == 400

    with pytest.raises(ValueError):
        ledger.reserve("tenant-b", 500)


def test_adapter_validates_and_parses_requests(tmp_path) -> None:
    csv_path = tmp_path / "requests.csv"
    pd.DataFrame(
        [
            {
                "request_id": "r1",
                "timestamp": "2026-01-01T00:00:00Z",
                "provider": "openai",
                "model": "gpt-4o",
                "tenant": "tenant-a",
                "input_tokens": 1000,
                "output_tokens": 200,
                "cached_input_tokens": 200,
                "original_status": "success",
            },
            {
                "request_id": "r2",
                "timestamp": "2026-01-01T00:00:01Z",
                "provider": "anthropic",
                "model": "claude-3.5-sonnet",
                "tenant": "tenant-b",
                "input_tokens": 500,
                "output_tokens": 100,
                "cached_input_tokens": 0,
                "original_status": "success",
            },
            {
                "request_id": "r3",
                "timestamp": "2026-01-01T00:00:02Z",
                "provider": "openai",
                "model": "gpt-4o",
                "tenant": "tenant-a",
                "input_tokens": -5,
                "output_tokens": 50,
                "cached_input_tokens": 0,
                "original_status": "success",
            },
        ]
    ).to_csv(csv_path, index=False)

    adapter = InputAdapter()
    rows, errors = adapter.load_csv(csv_path)

    assert len(rows) == 2
    assert isinstance(rows[0], RequestRow)
    assert rows[0].request_id == "r1"
    assert errors
    assert any("r3" in msg for msg in errors)
