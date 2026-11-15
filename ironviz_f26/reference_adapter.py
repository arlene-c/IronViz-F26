from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping

import pandas as pd

from .adapter import InputAdapter, RequestRow
from .money import Money
from .pricing import PriceCatalog, PriceRecord


@dataclass(frozen=True)
class ReferenceData:
    requests: tuple[RequestRow, ...]
    provenance: pd.DataFrame
    legacy_reference: pd.DataFrame
    prices: PriceCatalog
    compatibility_map: Mapping[tuple[str, str], tuple[str, str]]
    price_sources: pd.DataFrame
    rounding_reconciliation: dict[str, int | float]


def _micro_usd_per_million(value: object, column: str) -> int:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid {column} price {value!r}") from exc
    if not decimal_value.is_finite() or decimal_value < 0:
        raise ValueError(f"{column} prices must be finite and non-negative")
    micro_value = decimal_value * Decimal(1_000_000)
    if micro_value != micro_value.to_integral_value():
        raise ValueError(f"{column} price cannot be represented as integer micro-USD per 1M tokens: {value!r}")
    return int(micro_value)


def load_reference_prices(
    path: str | Path,
    model_providers: Mapping[str, str],
) -> tuple[PriceCatalog, dict[tuple[str, str], tuple[str, str]], pd.DataFrame]:
    frame = pd.read_csv(path, dtype={"model": "string", "cheaper_model": "string", "source": "string"})
    required = {
        "model",
        "input_per_million",
        "cached_input_per_million",
        "output_per_million",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Price CSV missing required columns: {', '.join(sorted(missing))}")
    if frame["model"].isna().any() or frame["model"].duplicated().any():
        raise ValueError("Price catalog model identifiers must be present and unique")

    records: dict[tuple[str, str], PriceRecord] = {}
    cheaper: dict[str, str] = {}
    source_rows: list[dict[str, str]] = []
    for row in frame.to_dict("records"):
        model = str(row["model"])
        input_price = _micro_usd_per_million(row["input_per_million"], "input")
        cached_price = _micro_usd_per_million(row["cached_input_per_million"], "cached input")
        output_price = _micro_usd_per_million(row["output_per_million"], "output")
        if cached_price > input_price:
            raise ValueError(f"Cached-input price exceeds input price for model {model!r}")
        cheaper_value = row.get("cheaper_model")
        cheaper_model = "" if pd.isna(cheaper_value) else str(cheaper_value).strip()
        provider = model_providers.get(model)
        if provider is not None:
            records[(provider, model)] = PriceRecord(
                provider=provider,
                model=model,
                input_price=input_price,
                cached_input_price=cached_price,
                output_price=output_price,
            )
            if cheaper_model:
                target_provider = model_providers.get(cheaper_model)
                if target_provider is None:
                    raise ValueError(f"Configured route target {cheaper_model!r} has no observed provider")
                cheaper[(provider, model)] = (target_provider, cheaper_model)
        source = row.get("source")
        source_rows.append({"model": model, "source": "" if pd.isna(source) else str(source)})

    for (provider, model), target_pair in cheaper.items():
        if target_pair not in records:
            raise ValueError(f"Route {provider}/{model} points to unpriced provider/model {target_pair!r}")
        source_record = records[(provider, model)]
        target_provider, target_model = target_pair
        target_record = records[(target_provider, target_model)]
        source_prices = (source_record.input_price, source_record.cached_input_price, source_record.output_price)
        target_prices = (target_record.input_price, target_record.cached_input_price, target_record.output_price)
        if any(target > source for source, target in zip(source_prices, target_prices)):
            raise ValueError(f"Configured cheaper model {target_model!r} is not componentwise cheaper than {model!r}")

    catalog = PriceCatalog(
        version=f"{Path(path).as_posix()} (source dates not declared in catalog)",
        rows=records,
    )
    return catalog, cheaper, pd.DataFrame(source_rows)


def load_reference_outputs(
    clean_path: str | Path,
    simulation_path: str | Path,
    price_path: str | Path,
) -> ReferenceData:
    clean = pd.read_csv(clean_path)
    simulated = pd.read_csv(simulation_path)
    required_clean = {"request_id", "timestamp", "provider", "model", "tenant", "input_tokens", "output_tokens", "cached_tokens", "exclude_reason"}
    if not required_clean.issubset(clean.columns):
        raise ValueError(f"Cleaned table missing columns: {', '.join(sorted(required_clean - set(clean.columns)))}")
    required_sim = {
        "request_id", "timestamp", "provider", "model", "tenant", "input_tokens", "output_tokens",
        "cached_tokens", "expected_output_tokens", "real_cost", "expected_cost",
    }
    if not required_sim.issubset(simulated.columns):
        raise ValueError(f"Simulation table missing columns: {', '.join(sorted(required_sim - set(simulated.columns)))}")
    eligible = clean[clean["exclude_reason"].fillna("").astype(str).eq("")].copy()
    if eligible["request_id"].duplicated().any():
        raise ValueError("Eligible cleaned requests contain duplicate request_id values")
    if simulated["request_id"].duplicated().any():
        raise ValueError("Reference simulation requests contain duplicate request_id values")

    clean_ids = set(eligible["request_id"].astype(str))
    simulated_ids = set(simulated["request_id"].astype(str))
    if clean_ids != simulated_ids:
        missing_from_sim = len(clean_ids - simulated_ids)
        missing_from_clean = len(simulated_ids - clean_ids)
        raise ValueError(
            f"Clean/reference row coverage differs: missing_from_simulation={missing_from_sim}, "
            f"missing_from_cleaned={missing_from_clean}"
        )
    eligible = eligible.sort_values(["timestamp", "request_id"], kind="stable").reset_index(drop=True)
    simulated = simulated.sort_values(["timestamp", "request_id"], kind="stable").reset_index(drop=True)
    if eligible["request_id"].astype(str).tolist() != simulated["request_id"].astype(str).tolist():
        raise ValueError("Cleaned and simulation request ordering differs")
    for column in ('provider', 'model', 'tenant', 'input_tokens', 'output_tokens', 'cached_tokens'):
        if not eligible[column].reset_index(drop=True).eq(simulated[column].reset_index(drop=True)).all():
            raise ValueError(f"Cleaned/reference attribute mismatch: {column}")
    if not pd.to_datetime(eligible.timestamp, utc=True, format='mixed').equals(pd.to_datetime(simulated.timestamp, utc=True, format='mixed')):
        raise ValueError("Cleaned/reference timestamp mismatch")

    provider_counts = eligible.groupby("model")["provider"].nunique()
    ambiguous_models = provider_counts[provider_counts > 1].index.tolist()
    if ambiguous_models:
        raise ValueError(f"Models map to multiple providers; explicit mapping required: {ambiguous_models}")
    model_providers = eligible.groupby("model")["provider"].first().astype(str).to_dict()
    catalog, compatibility, price_sources = load_reference_prices(price_path, model_providers)
    rows = pd.DataFrame(
        {
            "request_id": simulated["request_id"].astype(str),
            "timestamp": simulated["timestamp"].astype(str),
            "provider": simulated["provider"].astype(str),
            "model": simulated["model"].astype(str),
            "tenant": simulated["tenant"].astype(str),
            "input_tokens": simulated["input_tokens"],
            "output_tokens": simulated["output_tokens"],
            "cached_input_tokens": simulated["cached_tokens"],
            "original_status": "success",
        }
    )
    adapter = InputAdapter()
    requests, errors = adapter._coerce_dataframe(rows)
    if errors:
        raise ValueError("Canonical input validation failed: " + "; ".join(errors[:10]))
    if len(requests) != len(simulated):
        raise ValueError(f"Adapter coverage mismatch: {len(requests)} accepted from {len(simulated)} eligible rows")
    for request in requests:
        catalog.lookup(request.provider, request.model)

    canonical_costs = []
    for request in requests:
        price = catalog.lookup(request.provider, request.model)
        canonical_costs.append(
            Money.cost_for_tokens(request.input_tokens - request.cached_input_tokens, price.input_price)
            + Money.cost_for_tokens(request.cached_input_tokens, price.cached_input_price)
            + Money.cost_for_tokens(request.output_tokens, price.output_price)
        )
    canonical_total_micro = sum(canonical_costs)
    legacy_total_usd = float(simulated["real_cost"].sum())
    canonical_total_usd = canonical_total_micro / 1_000_000
    provenance_columns = [
        column for column in ("request_id", "provider", "status", "success", "exclude_reason", "reasoning_tokens")
        if column in clean.columns
    ]
    provenance = clean[provenance_columns].copy()
    reference_columns = [
        column for column in ("request_id", "expected_output_tokens", "expected_cost", "real_cost", "token_bucket")
        if column in simulated.columns
    ]
    legacy_reference = simulated[reference_columns].copy()
    return ReferenceData(
        requests=tuple(requests),
        provenance=provenance,
        legacy_reference=legacy_reference,
        prices=catalog,
        compatibility_map=compatibility,
        price_sources=price_sources,
        rounding_reconciliation={
            "eligible_requests": len(requests),
            "canonical_micro_usd_total": canonical_total_micro,
            "canonical_usd_total": canonical_total_usd,
            "legacy_unrounded_usd_total": legacy_total_usd,
            "difference_usd": canonical_total_usd - legacy_total_usd,
            "difference_pct_of_legacy": (canonical_total_usd - legacy_total_usd) / legacy_total_usd * 100
            if legacy_total_usd
            else 0.0,
        },
    )
