from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import math
import os
import time
if os.name != "nt":
    import resource

from ironviz_f26.engine import SimulationEngine
from ironviz_f26.estimators import GlobalEstimator
from ironviz_f26.experiments import modeled_request_cost
from ironviz_f26.fixture import generate_fixture
from ironviz_f26.policies import FCFS
from ironviz_f26.pricing import PriceCatalog, PriceRecord


def synthetic_catalog() -> PriceCatalog:
    return PriceCatalog(
        version="SYNTHETIC TEST DATA; not a historical price source",
        rows={
            ("openai", "gpt-4o"): PriceRecord("openai", "gpt-4o", 150, 40, 250),
            ("openai", "gpt-4o-mini"): PriceRecord("openai", "gpt-4o-mini", 80, 20, 120),
            ("anthropic", "claude-3.5-sonnet"): PriceRecord("anthropic", "claude-3.5-sonnet", 140, 35, 230),
        },
    )


def peak_working_set_bytes() -> int:
    if os.name == "nt":
        class ProcessMemoryCountersEx(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCountersEx),
            wintypes.DWORD,
        )
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        process = kernel32.GetCurrentProcess()
        ok = psapi.GetProcessMemoryInfo(
            process,
            ctypes.byref(counters),
            counters.cb,
        )
        if not ok:
            raise ctypes.WinError()
        return int(counters.PeakWorkingSetSize)

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if os.uname().sysname == "Darwin" else peak * 1024)


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure one synthetic FCFS replay and process peak memory.")
    parser.add_argument("--requests", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=26_031)
    parser.add_argument("--budget-fraction", type=float, default=0.7)
    args = parser.parse_args()
    if args.requests < 2 or not 0 < args.budget_fraction <= 1:
        parser.error("requests must be >=2 and budget-fraction must be in (0,1]")

    catalog = synthetic_catalog()
    preparation_started = time.perf_counter()
    requests = generate_fixture(seed=args.seed, n_requests=args.requests)
    training_count = max(1, args.requests // 5)
    training_costs = [modeled_request_cost(row, catalog) for row in requests[:training_count]]
    reference_cost = sum(modeled_request_cost(row, catalog) for row in requests)
    preparation_seconds = time.perf_counter() - preparation_started
    budget = int(reference_cost * args.budget_fraction)
    engine = SimulationEngine(
        catalog=catalog,
        policy=FCFS(),
        budget=budget,
        estimator=GlobalEstimator(training_costs),
        seed=args.seed,
        scenario_id="large-fcfs-synthetic-audit",
    )

    started = time.perf_counter()
    events = engine.run(requests)
    simulation_seconds = time.perf_counter() - started
    total_spend = sum(event.realized_cost for event in events)
    assert len(events) == args.requests
    assert total_spend == engine.ledger.global_spent
    assert engine.ledger.global_remaining + total_spend == budget
    assert engine.ledger.total_reserved() == 0
    assert 0 <= total_spend <= budget
    assert all(event.global_remaining >= 0 for event in events)

    print(f"data_label=SYNTHETIC TEST DATA")
    print(f"requests={len(requests)}")
    print(f"training_requests={training_count}")
    print(f"budget_fraction_modeled={args.budget_fraction}")
    print(f"reference_cost_micro_usd_modeled={reference_cost}")
    print(f"budget_micro_usd_modeled={budget}")
    print(f"admitted={sum(event.decision == 'ADMITTED' for event in events)}")
    print(f"completed_original={sum(event.outcome == 'COMPLETED_ORIGINAL' for event in events)}")
    print(f"rejected={sum(event.outcome == 'REJECTED' for event in events)}")
    print(f"truncated={sum(event.outcome == 'TRUNCATED_ORIGINAL' for event in events)}")
    print(f"realized_cost_micro_usd={total_spend}")
    print(f"global_remaining_micro_usd={engine.ledger.global_remaining}")
    print("strict_budget_reconciliation=PASS")
    print(f"fixture_and_reference_preparation_seconds={preparation_seconds:.6f}")
    print(f"fcfs_simulation_seconds={simulation_seconds:.6f}")
    print(f"process_peak_working_set_mib={peak_working_set_bytes() / (1024 * 1024):.3f}")


if __name__ == "__main__":
    main()
