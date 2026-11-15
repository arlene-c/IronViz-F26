from __future__ import annotations

from collections.abc import Iterable, Mapping
import math

import numpy as np


class GlobalEstimator:
    def __init__(self, costs: Iterable[int]):
        self.costs = list(costs)
        self._estimate = int(math.floor(float(np.mean(self.costs)))) if self.costs else None

    def estimate(self) -> int:
        if self._estimate is None:
            raise ValueError("No cost observations available")
        return self._estimate


class ModelConditionalEstimator:
    def __init__(self, costs_by_model: Mapping[str, Iterable[int]]):
        self.costs_by_model = {model: list(values) for model, values in costs_by_model.items()}
        self._estimates = {
            model: int(math.floor(float(np.mean(values))))
            for model, values in self.costs_by_model.items()
            if values
        }

    def estimate(self, model: str) -> int:
        if model not in self.costs_by_model:
            raise KeyError(f"No costs recorded for model {model!r}")
        if model not in self._estimates:
            raise ValueError(f"No cost observations for model {model!r}")
        return self._estimates[model]


class QuantileEstimator:
    def __init__(self, costs: Iterable[int], q: float = 0.5):
        self.costs = list(costs)
        if not 0 <= q <= 1:
            raise ValueError("q must be between 0 and 1")
        self.q = float(q)
        self._estimate = int(np.quantile(self.costs, self.q)) if self.costs else None

    def estimate(self) -> int:
        if self._estimate is None:
            raise ValueError("No cost observations available")
        return self._estimate
