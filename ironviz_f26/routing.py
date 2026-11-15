from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

import numpy as np

from .pricing import PriceCatalog
from .state import ObservableState, PreAdmissionView


ModelPair = tuple[str, str]


class RoutingWrapper:
    """Selective counterfactual routing around an existing admission policy."""

    def __init__(
        self,
        inner,
        *,
        compatibility_map: Mapping[ModelPair, ModelPair],
        eligibility_probability: float = 1.0,
        eligible_request_ids: Sequence[str] | None = None,
        trigger_rule: str = "always",
        theta: float = 0.5,
        mu_pair: float = math.log(0.8),
        sigma_pair: float = 0.1,
    ) -> None:
        if not 0 <= eligibility_probability <= 1:
            raise ValueError("eligibility_probability must be between 0 and 1")
        if trigger_rule not in {"always", "pressure"}:
            raise ValueError("trigger_rule must be 'always' or 'pressure'")
        if not 0 <= theta <= 1:
            raise ValueError("theta must be between 0 and 1")
        if sigma_pair < 0 or not math.isfinite(mu_pair) or not math.isfinite(sigma_pair):
            raise ValueError("routing lognormal parameters must be finite and sigma_pair non-negative")
        self.inner = inner
        self.compatibility_map = dict(compatibility_map)
        self.eligibility_probability = float(eligibility_probability)
        self.eligible_request_ids = frozenset(eligible_request_ids) if eligible_request_ids is not None else None
        self.trigger_rule = trigger_rule
        self.theta = float(theta)
        self.mu_pair = float(mu_pair)
        self.sigma_pair = float(sigma_pair)
        self.label = f"{inner.__class__.__name__}+Routing"
        self.reset({})

    def reset(self, cfg: dict | None = None) -> None:
        self.cfg = cfg or {}
        self.budget = int(self.cfg.get("budget", 0))
        self.inner.reset(self.cfg)

    def prepare_run(self, request_count: int, seed: int) -> None:
        rng = np.random.default_rng(np.random.SeedSequence(int(seed), spawn_key=(2,)))
        self._eligibility_draws = rng.random(request_count)
        self._length_multipliers = rng.lognormal(self.mu_pair, self.sigma_pair, request_count)

    def route_for(
        self,
        index: int,
        view: PreAdmissionView,
        state: ObservableState,
        catalog: PriceCatalog,
    ) -> tuple[str, str, float] | None:
        if self.eligible_request_ids is not None:
            eligible = view.request_id in self.eligible_request_ids
        else:
            eligible = self._eligibility_draws[index] < self.eligibility_probability
        if not eligible:
            return None

        pressure = 1.0 if self.budget <= 0 else 1.0 - state.global_remaining / self.budget
        if self.trigger_rule == "pressure" and pressure <= self.theta:
            return None

        original_pair = (view.provider, view.model)
        target_pair = self.compatibility_map.get(original_pair)
        if target_pair is None:
            return None
        original_price = catalog.lookup(*original_pair)
        target_price = catalog.lookup(*target_pair)
        original_components = (
            original_price.input_price,
            original_price.cached_input_price,
            original_price.output_price,
        )
        target_components = (
            target_price.input_price,
            target_price.cached_input_price,
            target_price.output_price,
        )
        if any(target > original for target, original in zip(target_components, original_components)):
            raise ValueError(f"Configured route {original_pair!r} -> {target_pair!r} is not cheaper componentwise")
        if target_components == original_components:
            raise ValueError(f"Configured route {original_pair!r} -> {target_pair!r} does not reduce any price")
        return target_pair[0], target_pair[1], float(self._length_multipliers[index])

    def decide(self, view: PreAdmissionView, state: ObservableState) -> bool:
        return bool(self.inner.decide(view, state))

    def observe(self, outcome: str, state: ObservableState) -> None:
        self.inner.observe(outcome, state)
