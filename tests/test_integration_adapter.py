from __future__ import annotations

import pandas as pd
import pytest

from ironviz_f26.reference_adapter import load_reference_outputs, load_reference_prices


def test_reference_adapter_converts_prices_and_preserves_provenance(tmp_path) -> None:
    clean_path = tmp_path / "clean.csv"
    simulation_path = tmp_path / "requests_sim.csv"
    prices_path = tmp_path / "prices.csv"
    pd.DataFrame(
        [
            {
                "request_id": "r1",
                "timestamp": "2026-10-01T00:00:00.000000Z",
                "provider": "OpenAI",
                "model": "gpt-4o",
                "tenant": "tenant-a",
                "status": 200,
                "success": True,
                "input_tokens": 3,
                "output_tokens": 1,
                "cached_tokens": 1,
                "reasoning_tokens": 0,
                "exclude_reason": "",
            },
            {
                "request_id": "r2",
                "timestamp": "2026-10-01T00:00:00.500000Z",
                "provider": "OpenAI",
                "model": "gpt-4o-mini",
                "tenant": "tenant-a",
                "status": 200,
                "success": True,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
                "exclude_reason": "",
            },
            {
                "request_id": "r3",
                "timestamp": "2026-10-01T00:00:01.000000Z",
                "provider": "OpenAI",
                "model": "gpt-4o",
                "tenant": "tenant-a",
                "status": 400,
                "success": False,
                "input_tokens": None,
                "output_tokens": None,
                "cached_tokens": None,
                "reasoning_tokens": None,
                "exclude_reason": "failed call",
            },
        ]
    ).to_csv(clean_path, index=False)
    pd.DataFrame(
        [
            {
                "request_id": "r1",
                "timestamp": "2026-10-01T00:00:00.000000Z",
                "provider": "OpenAI",
                "model": "gpt-4o",
                "tenant": "tenant-a",
                "input_tokens": 3,
                "cached_tokens": 1,
                "output_tokens": 1,
                "expected_output_tokens": 1,
                "real_cost": 0.00001625,
                "expected_cost": 0.00001625,
                "token_bucket": "Small",
            },
            {
                "request_id": "r2",
                "timestamp": "2026-10-01T00:00:00.500000Z",
                "provider": "OpenAI",
                "model": "gpt-4o-mini",
                "tenant": "tenant-a",
                "input_tokens": 0,
                "cached_tokens": 0,
                "output_tokens": 0,
                "expected_output_tokens": 0,
                "real_cost": 0,
                "expected_cost": 0,
                "token_bucket": "Small",
            }
        ]
    ).to_csv(simulation_path, index=False)
    pd.DataFrame(
        [
            {"model": "gpt-4o", "input_per_million": 2.5, "cached_input_per_million": 1.25, "output_per_million": 10, "cheaper_model": "gpt-4o-mini", "source": "provider source"},
            {"model": "gpt-4o-mini", "input_per_million": 0.15, "cached_input_per_million": 0.075, "output_per_million": 0.6, "cheaper_model": "", "source": "provider source"},
        ]
    ).to_csv(prices_path, index=False)

    adapted = load_reference_outputs(clean_path, simulation_path, prices_path)

    assert len(adapted.requests) == 2
    assert adapted.requests[0].cached_input_tokens == 1
    assert adapted.requests[0].original_status == "success"
    assert len(adapted.provenance) == 3
    assert len(adapted.legacy_reference) == 2
    assert adapted.prices.lookup("OpenAI", "gpt-4o").input_price == 2_500_000
    assert adapted.prices.lookup("OpenAI", "gpt-4o-mini").output_price == 600_000
    assert adapted.compatibility_map[("OpenAI", "gpt-4o")] == ("OpenAI", "gpt-4o-mini")
    assert adapted.rounding_reconciliation["canonical_micro_usd_total"] == 17
    assert adapted.rounding_reconciliation["legacy_unrounded_usd_total"] == 0.00001625
    assert adapted.rounding_reconciliation["difference_usd"] == pytest.approx(0.00000075)


def test_reference_price_loader_rejects_non_cheaper_configured_route(tmp_path) -> None:
    prices_path = tmp_path / "prices.csv"
    pd.DataFrame(
        [
            {"model": "model-a", "input_per_million": 1, "cached_input_per_million": 1, "output_per_million": 1, "cheaper_model": "model-b", "source": "test"},
            {"model": "model-b", "input_per_million": 2, "cached_input_per_million": 1, "output_per_million": 1, "cheaper_model": "", "source": "test"},
        ]
    ).to_csv(prices_path, index=False)

    with pytest.raises(ValueError, match="not componentwise cheaper"):
        load_reference_prices(prices_path, {"model-a": "OpenAI", "model-b": "OpenAI"})
