from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ironviz_f26.reference_adapter import load_reference_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Adapt prepared cleaned/reference outputs to the modular simulator contract.")
    parser.add_argument("--clean", default="results/clean_requests.csv")
    parser.add_argument("--simulation", default="results/requests_sim.csv")
    parser.add_argument("--prices", default="config/prices.csv")
    parser.add_argument("--output-dir", default="outputs/canonical_reference")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    adapted = load_reference_outputs(args.clean, args.simulation, args.prices)

    pd.DataFrame([asdict(request) for request in adapted.requests]).to_csv(
        output_dir / "canonical_requests.csv", index=False
    )
    adapted.provenance.to_parquet(output_dir / "request_provenance.parquet", index=False)
    adapted.legacy_reference.to_parquet(output_dir / "legacy_reference_costs.parquet", index=False)
    adapted.price_sources.to_csv(output_dir / "price_sources.csv", index=False)

    catalog_payload = {
        "version": adapted.prices.version,
        "price_unit": "integer micro-USD per 1M tokens",
        "rows": [
            {
                "provider": record.provider,
                "model": record.model,
                "input_price": record.input_price,
                "cached_input_price": record.cached_input_price,
                "output_price": record.output_price,
            }
            for record in adapted.prices._rows.values()
        ],
    }
    (output_dir / "price_catalog_micro_usd.json").write_text(
        json.dumps(catalog_payload, indent=2), encoding="utf-8"
    )
    route_payload = [
        {
            "source_provider": source[0],
            "source_model": source[1],
            "target_provider": target[0],
            "target_model": target[1],
            "status": "modeled compatibility assumption from config/prices.csv",
        }
        for source, target in sorted(adapted.compatibility_map.items())
    ]
    (output_dir / "routing_compatibility.json").write_text(json.dumps(route_payload, indent=2), encoding="utf-8")

    report = {
        "data_label": "CLEANED REFERENCE OUTPUT; synthetic telemetry as labeled by data-team analysis",
        "input_files": {
            "cleaned": str(args.clean),
            "simulation_reference": str(args.simulation),
            "price_catalog": str(args.prices),
        },
        "eligible_request_count": len(adapted.requests),
        "provenance_row_count": len(adapted.provenance),
        "legacy_reference_row_count": len(adapted.legacy_reference),
        "price_catalog_version": adapted.prices.version,
        "price_source_dates": "not supplied in config/prices.csv",
        "rounding_reconciliation": adapted.rounding_reconciliation,
        "routing_compatibility_pairs": len(adapted.compatibility_map),
        "outputs": [
            "canonical_requests.csv",
            "request_provenance.parquet",
            "legacy_reference_costs.parquet",
            "price_sources.csv",
            "price_catalog_micro_usd.json",
            "routing_compatibility.json",
            "adaptation_report.json",
        ],
    }
    (output_dir / "adaptation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
