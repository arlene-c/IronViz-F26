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
        column_positions = {column: index + 1 for index, column in enumerate(df.columns)}
        timestamps = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        token_columns = ("input_tokens", "output_tokens", "cached_input_tokens")
        token_values = {
            column: pd.to_numeric(df[column], errors="coerce").to_numpy(dtype=float)
            for column in token_columns
        }
        reference_values = (
            pd.to_numeric(df["reference_cost"], errors="coerce").to_numpy(dtype=float)
            if "reference_cost" in df.columns
            else None
        )

        for position, row in enumerate(df.itertuples(index=True, name=None)):
            index = row[0]
            get_value = lambda column: row[column_positions[column]]
            if pd.isna(get_value("request_id")):
                errors.append(f"Row {index}: request_id is blank")
                continue
            request_id = str(get_value("request_id")).strip()
            if not request_id:
                errors.append(f"Row {index}: request_id is blank")
                continue
            if request_id in seen_ids:
                errors.append(f"Row {index}: duplicate request_id '{request_id}'")
                continue
            seen_ids.add(request_id)

            timestamp_value = timestamps.iloc[position]
            if pd.isna(timestamp_value):
                errors.append(f"Row {index}: invalid timestamp for request_id '{request_id}'")
                continue
            if previous_timestamp is not None and timestamp_value < previous_timestamp:
                errors.append(f"Row {index}: timestamp is out of chronological order for request_id '{request_id}'")
                continue
            previous_timestamp = timestamp_value

            required_text = ("provider", "model", "tenant", "original_status")
            if any(pd.isna(get_value(column)) or not str(get_value(column)).strip() for column in required_text):
                errors.append(f"Row {index}: provider, model, tenant, and original_status must be nonblank for request_id '{request_id}'")
                continue

            request_token_values = [token_values[column][position] for column in token_columns]
            if any(not math.isfinite(value) or not value.is_integer() for value in request_token_values):
                errors.append(f"Row {index}: token counts must be integers for request_id '{request_id}'")
                continue
            input_tokens, output_tokens, cached_input_tokens = (int(value) for value in request_token_values)

            if input_tokens < 0 or output_tokens < 0 or cached_input_tokens < 0:
                errors.append(f"Row {index}: token counts must be non-negative for request_id '{request_id}'")
                continue
            if cached_input_tokens > input_tokens:
                errors.append(f"Row {index}: cached_input_tokens exceeds input_tokens for request_id '{request_id}'")
                continue

            reference_cost = None
            if reference_values is not None and not pd.isna(reference_values[position]):
                reference_numeric = float(reference_values[position])
                if not math.isfinite(reference_numeric) or not reference_numeric.is_integer() or reference_numeric < 0:
                    errors.append(f"Row {index}: reference_cost must be a non-negative integer for request_id '{request_id}'")
                    continue
                reference_cost = int(reference_numeric)

            rows.append(
                RequestRow(
                    request_id=request_id,
                    timestamp=str(get_value("timestamp")),
                    provider=str(get_value("provider")),
                    model=str(get_value("model")),
                    tenant=str(get_value("tenant")),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_input_tokens=cached_input_tokens,
                    original_status=str(get_value("original_status")),
                    reference_cost=reference_cost,
                )
            )

        return rows, errors
