from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np


def generate_fixture(
    seed: int,
    n_requests: int = 40,
    tenants: list[str] | tuple[str, ...] = ("tenant-a", "tenant-b", "tenant-c"),
    providers: list[str] | tuple[str, ...] = ("openai", "anthropic"),
    requests_per_day: int = 24,
) -> list[dict[str, object]]:
    if requests_per_day < 1:
        raise ValueError("requests_per_day must be positive")
    if not tenants or not providers:
        raise ValueError("tenants and providers must each contain at least one value")
    rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(0,)))
    rows: list[dict[str, object]] = []
    start = datetime(2026, 1, 1, 0, 0, 0)

    for idx in range(n_requests):
        tenant = tenants[idx % len(tenants)]
        if idx % 5 == 0 and tenants:
            tenant = tenants[0]
        provider = providers[idx % len(providers)]
        if provider == "openai":
            model = "gpt-4o-mini" if idx % 3 == 0 else "gpt-4o"
        else:
            model = "claude-3.5-sonnet"
        size = max(200, int(rng.lognormal(mean=6.8, sigma=1.1)))
        output_size = max(1, int(rng.lognormal(mean=3.2, sigma=0.8)))
        burst_offset = int(rng.integers(0, 60))
        timestamp = (
            start
            + timedelta(days=idx // requests_per_day, seconds=(idx % requests_per_day) * 60 + burst_offset)
        ).isoformat() + "Z"
        cached = min(size, max(0, int(rng.integers(0, max(1, size // 3)))))
        rows.append(
            {
                "request_id": f"req-{idx:04d}",
                "timestamp": timestamp,
                "provider": provider,
                "model": model,
                "tenant": tenant,
                "input_tokens": int(size),
                "output_tokens": int(output_size),
                "cached_input_tokens": int(cached),
                "original_status": "success",
            }
        )

    rows.sort(key=lambda row: row["timestamp"])  # type: ignore[arg-type]
    return rows
