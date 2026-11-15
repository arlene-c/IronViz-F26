from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

import pandas as pd

from .adapter import InputAdapter
from .experiments import DEFAULT_POLICIES, ExperimentConfig, ExperimentRunner
from .fixture import generate_fixture
from .outputs import generate_findings, write_diagnostics, write_outputs
from .pricing import PriceCatalog, PriceRecord
from .experiments import ExperimentResults


def synthetic_catalog() -> PriceCatalog:
    return PriceCatalog(
        version="SYNTHETIC TEST DATA; not sourced from a provider price sheet",
        rows={
            ("openai", "gpt-4o"): PriceRecord("openai", "gpt-4o", 150, 40, 250),
            ("openai", "gpt-4o-mini"): PriceRecord("openai", "gpt-4o-mini", 80, 20, 120),
            ("anthropic", "claude-3.5-sonnet"): PriceRecord("anthropic", "claude-3.5-sonnet", 140, 35, 230),
        },
    )


def _catalog_json(catalog: PriceCatalog) -> dict:
    return {
        "version": catalog.version,
        "price_unit": "integer micro-USD per 1M tokens",
        "rows": [
            {
                "provider": record.provider,
                "model": record.model,
                "input_price": record.input_price,
                "cached_input_price": record.cached_input_price,
                "output_price": record.output_price,
            }
            for record in catalog._rows.values()
        ],
    }


def load_catalog(path: str | Path) -> PriceCatalog:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("price_unit") != "integer micro-USD per 1M tokens":
        raise ValueError("invalid catalog price_unit")
    rows = {}
    for item in payload["rows"]:
        record = PriceRecord(
            provider=str(item["provider"]),
            model=str(item["model"]),
            input_price=item["input_price"],
            cached_input_price=item["cached_input_price"],
            output_price=item["output_price"],
        )
        if (record.provider, record.model) in rows:
            raise ValueError(f"duplicate catalog pair: {record.provider}/{record.model}")
        rows[(record.provider, record.model)] = record
    return PriceCatalog(version=str(payload["version"]), rows=rows)


def _load_rows(path: str | Path) -> tuple[list, list[str]]:
    adapter = InputAdapter()
    suffix = Path(path).suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return adapter.load_parquet(path)
    if suffix == ".csv":
        return adapter.load_csv(path)
    raise ValueError("input must be a CSV or Parquet file")


def _record_errors(path: str | Path, errors: Sequence[str]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"row_error": list(errors)}, columns=["row_error"]).to_csv(destination, index=False)
    return destination


def _float_list(value: str) -> tuple[float, ...]:
    try:
        return tuple(float(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a comma-separated list of numbers") from exc


def _policy_list(value: str) -> tuple[str, ...]:
    names = tuple(item.strip() for item in value.split(",") if item.strip())
    unknown = set(names) - set(DEFAULT_POLICIES)
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown policy names: {', '.join(sorted(unknown))}")
    if not names:
        raise argparse.ArgumentTypeError("at least one policy is required")
    return names


def _model_caps(value: str) -> dict[str, int]:
    caps: dict[str, int] = {}
    try:
        for item in value.split(","):
            if not item.strip():
                continue
            model, cap = item.split(":", 1)
            caps[model.strip()] = int(cap)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("model caps must be comma-separated model:integer pairs") from exc
    return caps


def _load_routing_compatibility(path: str | None) -> tuple[tuple[str, str, str, str], ...]:
    if not path:
        return ()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(
        (
            str(item["source_provider"]),
            str(item["source_model"]),
            str(item["target_provider"]),
            str(item["target_model"]),
        )
        for item in payload
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ironviz", description="Deterministic scarcity simulation and experiment tools")
    commands = parser.add_subparsers(dest="command", required=True)

    fixture = commands.add_parser("generate-fixture", help="write deterministic SYNTHETIC TEST DATA")
    fixture.add_argument("--output", required=True)
    fixture.add_argument("--price-catalog-output")
    fixture.add_argument("--seed", type=int, default=2026)
    fixture.add_argument("--requests", type=int, default=48)
    fixture.add_argument("--requests-per-day", type=int, default=24)

    validate = commands.add_parser("validate-data", help="validate cleaned CSV/Parquet request rows")
    validate.add_argument("--input", required=True)
    validate.add_argument("--error-report", default="row_errors.csv")

    simulation = commands.add_parser("run-simulation", help="run one policy on the post-training replay window")
    simulation.add_argument("--input", required=True)
    simulation.add_argument("--price-catalog", required=True)
    simulation.add_argument("--output-dir", required=True)
    simulation.add_argument("--policy", choices=DEFAULT_POLICIES, default="FCFS")
    simulation.add_argument("--budget-fraction", type=float, default=0.7)
    simulation.add_argument("--training-fraction", type=float, default=0.2)
    simulation.add_argument("--seed", type=int, default=2026)
    simulation.add_argument("--data-label", default="USER-PROVIDED CLEANED INPUT")
    simulation.add_argument("--reservation-mode", choices=("mean", "quantile", "cap"), default="mean")
    simulation.add_argument("--reservation-quantile", type=float, default=0.9)
    simulation.add_argument("--output-cap", type=int, default=1024)
    simulation.add_argument("--model-output-caps", type=_model_caps, default={})
    simulation.add_argument("--routing-compatibility")
    simulation.add_argument("--timeseries-stride", type=int, default=1)

    experiments = commands.add_parser("run-experiments", help="run paired replay/day-block bootstrap experiments")
    experiments.add_argument("--input", required=True)
    experiments.add_argument("--price-catalog", required=True)
    experiments.add_argument("--output-dir", required=True)
    experiments.add_argument("--budget-fractions", type=_float_list, default=(0.5, 0.7, 0.85, 1.0))
    experiments.add_argument("--replicates", type=int, default=3)
    experiments.add_argument("--training-fraction", type=float, default=0.2)
    experiments.add_argument("--seed", type=int, default=2026)
    experiments.add_argument("--demand-imbalance", type=_float_list, default=(1.0, 1.5))
    experiments.add_argument("--estimator-noise", type=_float_list, default=(0.0,))
    experiments.add_argument("--routing-eligibility", type=_float_list, default=(0.0, 0.5, 1.0))
    experiments.add_argument("--reservation-multipliers", type=_float_list, default=(1.0,))
    experiments.add_argument("--routed-output-multipliers", type=_float_list, default=(0.7,))
    experiments.add_argument("--routing-sigma", type=float, default=0.0)
    experiments.add_argument("--policies", type=_policy_list, default=DEFAULT_POLICIES)
    experiments.add_argument("--no-bootstrap", action="store_true")
    experiments.add_argument("--no-traces", action="store_true")
    experiments.add_argument("--data-label", default="USER-PROVIDED CLEANED INPUT")
    experiments.add_argument("--reservation-mode", choices=("mean", "quantile", "cap"), default="mean")
    experiments.add_argument("--reservation-quantile", type=float, default=0.9)
    experiments.add_argument("--output-cap", type=int, default=1024)
    experiments.add_argument("--model-output-caps", type=_model_caps, default={})
    experiments.add_argument("--trace-policies", type=_policy_list)
    experiments.add_argument("--timeseries-stride", type=int, default=1)
    experiments.add_argument("--bootstrap-method", choices=("day_block", "local_12h"), default="day_block")
    experiments.add_argument("--bootstrap-window-days", type=float, default=3.0)
    experiments.add_argument("--bootstrap-block-hours", type=int, default=12)
    experiments.add_argument("--routing-compatibility")
    for command in (simulation, experiments):
        command.add_argument("--tenant-roster", help="comma-separated configured tenants; defaults to training tenants only")
        command.add_argument("--horizon-start", help="configured ISO budget horizon start; required for timed policies")
        command.add_argument("--horizon-end", help="configured ISO budget horizon end; required for timed policies")

    report = commands.add_parser("generate-report", help="regenerate findings and diagnostic charts from output tables")
    report.add_argument("--output-dir", required=True)

    return parser


def _load_valid_input(path: str, error_path: str) -> list:
    rows, errors = _load_rows(path)
    _record_errors(error_path, errors)
    if errors:
        raise ValueError(f"input has {len(errors)} validation error(s); see {error_path}")
    return rows


def _config_from_args(args: argparse.Namespace, *, policies: tuple[str, ...] | None = None) -> ExperimentConfig:
    return ExperimentConfig(
        budget_fractions=tuple(args.budget_fractions),
        replicates=args.replicates,
        seed=args.seed,
        training_fraction=args.training_fraction,
        bootstrap=not args.no_bootstrap,
        demand_imbalance=tuple(args.demand_imbalance),
        estimator_noise=tuple(args.estimator_noise),
        routing_eligibility=tuple(args.routing_eligibility),
        reservation_multipliers=tuple(args.reservation_multipliers),
        routed_output_multipliers=tuple(args.routed_output_multipliers),
        routing_sigma=args.routing_sigma,
        policies=policies or tuple(args.policies),
        reservation_mode=args.reservation_mode,
        reservation_quantile=args.reservation_quantile,
        output_cap=args.output_cap,
        model_output_caps=args.model_output_caps,
        trace_policies=getattr(args, "trace_policies", None),
        trace_replicates=() if getattr(args, "no_traces", False) else (0, 1),
        timeseries_stride=args.timeseries_stride,
        bootstrap_method=getattr(args, "bootstrap_method", "day_block"),
        bootstrap_window_days=getattr(args, "bootstrap_window_days", 3.0),
        bootstrap_block_hours=getattr(args, "bootstrap_block_hours", 12),
        routing_compatibility=_load_routing_compatibility(args.routing_compatibility),
        data_label=args.data_label,
        tenant_roster=tuple(t.strip() for t in (args.tenant_roster or '').split(',') if t.strip()),
        horizon_start=args.horizon_start,
        horizon_end=args.horizon_end,
    )


def _run(args: argparse.Namespace) -> int:
    if args.command == "generate-fixture":
        rows = generate_fixture(seed=args.seed, n_requests=args.requests, requests_per_day=args.requests_per_day)
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(destination, index=False)
        catalog_path = Path(args.price_catalog_output) if args.price_catalog_output else None
        if catalog_path:
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(_catalog_json(synthetic_catalog()), indent=2), encoding="utf-8")
        print(json.dumps({"data_label": "SYNTHETIC TEST DATA", "requests": len(rows), "output": str(destination), "price_catalog": str(catalog_path) if catalog_path else None}))
        return 0

    if args.command == "validate-data":
        rows, errors = _load_rows(args.input)
        report = _record_errors(args.error_report, errors)
        print(json.dumps({"valid_rows": len(rows), "row_errors": len(errors), "error_report": str(report)}))
        return 1 if errors else 0

    if args.command in {"run-simulation", "run-experiments"}:
        error_path = Path(args.output_dir) / "row_errors.csv"
        rows = _load_valid_input(args.input, str(error_path))
        catalog = load_catalog(args.price_catalog)
        if args.command == "run-simulation":
            config = ExperimentConfig(
                budget_fractions=(args.budget_fraction,),
                replicates=1,
                seed=args.seed,
                training_fraction=args.training_fraction,
                bootstrap=False,
                demand_imbalance=(1.0,),
                estimator_noise=(0.0,),
                routing_eligibility=(0.5,),
                reservation_multipliers=(1.0,),
                routed_output_multipliers=(0.7,),
                policies=(args.policy,),
                trace_replicates=(0,),
                reservation_mode=args.reservation_mode,
                reservation_quantile=args.reservation_quantile,
                output_cap=args.output_cap,
                model_output_caps=args.model_output_caps,
                timeseries_stride=args.timeseries_stride,
                routing_compatibility=_load_routing_compatibility(args.routing_compatibility),
                data_label=args.data_label,
                tenant_roster=tuple(t.strip() for t in (args.tenant_roster or '').split(',') if t.strip()),
                horizon_start=args.horizon_start,
                horizon_end=args.horizon_end,
            )
        else:
            config = _config_from_args(args)
        results = ExperimentRunner(catalog, config).run(rows)
        paths = write_outputs(results, args.output_dir)
        print(json.dumps({
            "runs": len(results.run_metrics),
            "scenarios": len(results.scenario_metadata["scenarios"]),
            "experiment_runtime_seconds": results.scenario_metadata["experiment_runtime_seconds"],
            "outputs": [str(path) for path in paths],
        }))
        return 0

    if args.command == "generate-report":
        output_dir = Path(args.output_dir)
        summary = pd.read_csv(output_dir / "experiment_summary.csv")
        comparisons = pd.read_csv(output_dir / "policy_comparisons.csv")
        metadata = json.loads((output_dir / "scenario_metadata.json").read_text(encoding="utf-8"))
        (output_dir / "findings.md").write_text(generate_findings(summary, comparisons, metadata), encoding="utf-8")
        def read_table(filename: str, parquet: bool = False) -> pd.DataFrame:
            path = output_dir / filename
            if not path.exists():
                return pd.DataFrame()
            return pd.read_parquet(path) if parquet else pd.read_csv(path)
        results = ExperimentResults(
            run_metrics=read_table("run_metrics.csv"),
            tenant_metrics=read_table("tenant_metrics.csv"),
            experiment_summary=summary,
            policy_comparisons=comparisons,
            regime_map=read_table("regime_map.csv"),
            budget_timeseries=read_table("budget_timeseries.parquet", parquet=True),
            event_traces=read_table("event_traces.parquet", parquet=True),
            scenario_metadata=metadata,
        )
        paths = write_diagnostics(results, output_dir)
        print(json.dumps({"report": str(output_dir / "findings.md"), "charts": [str(path) for path in paths]}))
        return 0

    raise ValueError(f"unsupported command {args.command!r}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
