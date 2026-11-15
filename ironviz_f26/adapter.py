from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
from typing import Iterable

import pandas as pd


@dataclass(frozen=True, slots=True)
class RequestRow:
    request_id: str
    timestamp: str
    provider: str
    model: str
    tenant: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    original_status: str
    reference_cost: int | None = None


class InputAdapter:
    """Validate and normalize raw request CSV/Parquet input."""

    REQUIRED_COLUMNS = {
        "request_id",
        "timestamp",
        "provider",
        "model",
        "tenant",
        "input_tokens",
        "output_tokens",
        "cached_input_tokens",
        "original_status",
    }

    def load_csv(self, path: str | Path) -> tuple[list[RequestRow], list[str]]:
        df = pd.read_csv(path)
        return self._coerce_dataframe(df)

    def load_parquet(self, path: str | Path) -> tuple[list[RequestRow], list[str]]:
        df = pd.read_parquet(path)
        return self._coerce_dataframe(df)

    def _coerce_dataframe(self, df: pd.DataFrame) -> tuple[list[RequestRow], list[str]]:
        errors: list[str] = []
        missing = sorted(self.REQUIRED_COLUMNS - set(df.columns))
        if missing:
            errors.append(f"Missing required columns: {', '.join(missing)}")
            return [], errors

        seen_ids: set[str] = set()
        rows: list[RequestRow] = []
        previous_timestamp = None

        for index, row in df.iterrows():
            if pd.isna(row["request_id"]):
                errors.append(f"Row {index}: request_id is blank")
                continue
            request_id = str(row["request_id"]).strip()
            if not request_id:
                errors.append(f"Row {index}: request_id is blank")
                continue
            if request_id in seen_ids:
                errors.append(f"Row {index}: duplicate request_id '{request_id}'")
                continue
            seen_ids.add(request_id)

            try:
                timestamp_value = pd.to_datetime(row["timestamp"], errors="raise", utc=True)
            except Exception:
                errors.append(f"Row {index}: invalid timestamp for request_id '{request_id}'")
                continue
            if previous_timestamp is not None and timestamp_value < previous_timestamp:
                errors.append(f"Row {index}: timestamp is out of chronological order for request_id '{request_id}'")
                continue
            previous_timestamp = timestamp_value

            required_text = ("provider", "model", "tenant", "original_status")
            if any(pd.isna(row[column]) or not str(row[column]).strip() for column in required_text):
                errors.append(f"Row {index}: provider, model, tenant, and original_status must be nonblank for request_id '{request_id}'")
                continue

            try:
                token_values = [float(row[column]) for column in ("input_tokens", "output_tokens", "cached_input_tokens")]
                if any(not math.isfinite(value) or not value.is_integer() for value in token_values):
                    raise ValueError("token counts must be integral")
                input_tokens, output_tokens, cached_input_tokens = (int(value) for value in token_values)
            except (TypeError, ValueError):
                errors.append(f"Row {index}: token counts must be integers for request_id '{request_id}'")
                continue

            if input_tokens < 0 or output_tokens < 0 or cached_input_tokens < 0:
                errors.append(f"Row {index}: token counts must be non-negative for request_id '{request_id}'")
                continue
            if cached_input_tokens > input_tokens:
                errors.append(f"Row {index}: cached_input_tokens exceeds input_tokens for request_id '{request_id}'")
                continue

            reference_cost = None
            if "reference_cost" in df.columns and not pd.isna(row["reference_cost"]):
                try:
                    reference_numeric = float(row["reference_cost"])
                    if not math.isfinite(reference_numeric) or not reference_numeric.is_integer() or reference_numeric < 0:
                        raise ValueError("reference_cost must be a non-negative integer")
                    reference_cost = int(reference_numeric)
                except (TypeError, ValueError):
                    errors.append(f"Row {index}: reference_cost must be a non-negative integer for request_id '{request_id}'")
                    continue

            rows.append(
                RequestRow(
                    request_id=request_id,
                    timestamp=str(row["timestamp"]),
                    provider=str(row["provider"]),
                    model=str(row["model"]),
                    tenant=str(row["tenant"]),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_input_tokens=cached_input_tokens,
                    original_status=str(row["original_status"]),
                    reference_cost=reference_cost,
                )
            )

        return rows, errors
