"""CLI for ordinary-bowing baseline engine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def register_baseline_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    base = subparsers.add_parser("baseline", help="Ordinary-bowing baseline engine (Phase 2)")
    sub = base.add_subparsers(dest="baseline_command", required=True)

    build = sub.add_parser("build", help="Build an ordinary-bowing baseline")
    build.add_argument("--collections", nargs="+", default=None, help="Baseline collection IDs")
    build.add_argument("--metric-definition", default=None, dest="metric_definition")
    build.add_argument("--pooling-method", default=None)
    build.add_argument("--run-config", type=Path, default=None)
    build.add_argument("--output-dir", type=Path, default=None)
    build.add_argument("--dry-run", action="store_true")
    build.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=True)
    build.add_argument("--seed", type=int, default=None)
    build.add_argument("--strict", action="store_true")
    build.add_argument("--instrument", nargs="+", default=None, dest="instruments")
    build.add_argument("--dynamic", nargs="+", default=None, dest="dynamics")
    build.add_argument("--pitch-min", type=float, default=None)
    build.add_argument("--pitch-max", type=float, default=None)
    build.add_argument("--no-wide", action="store_true", help="Skip wide Excel exports")

    inspect_p = sub.add_parser("inspect", help="Inspect baseline run configuration")
    inspect_p.add_argument("--run-config", type=Path, default=None)

    validate_p = sub.add_parser("validate", help="Validate baseline run configuration")
    validate_p.add_argument("--run-config", type=Path, default=None)

    compare = sub.add_parser("compare-methods", help="Compare pooling methods (dry-run)")
    compare.add_argument("--collections", nargs="+", required=True)
    compare.add_argument("--methods", nargs="+", required=True)
    compare.add_argument("--metric-definition", default=None, dest="metric_definition")
    compare.add_argument("--run-config", type=Path, default=None)


def run_baseline_command(args: argparse.Namespace) -> int:
    from string_technique_model.baseline import pipeline

    cmd = args.baseline_command
    if cmd == "inspect":
        print(json.dumps(pipeline.inspect_baseline_config(args.run_config), indent=2, default=str))
        return 0
    if cmd == "validate":
        payload = pipeline.validate_baseline_config(args.run_config)
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1
    if cmd == "compare-methods":
        payload = pipeline.compare_pooling_methods(
            args.collections,
            args.methods,
            run_config_path=args.run_config,
            metric_definition_id=args.metric_definition,
        )
        print(json.dumps(payload, indent=2, default=str))
        return 0
    if cmd == "build":
        result = pipeline.build_ordinary_baseline(
            args.run_config,
            collection_ids=args.collections,
            metric_definition_id=args.metric_definition,
            pooling_method=args.pooling_method,
            instruments=args.instruments,
            dynamics=args.dynamics,
            pitch_min=args.pitch_min,
            pitch_max=args.pitch_max,
            output_dir=args.output_dir,
            dry_run=bool(args.dry_run),
            overwrite=bool(args.overwrite),
            seed=args.seed,
            strict=bool(args.strict),
            write_wide=False if args.no_wide else None,
        )
        summary = {
            "run_id": result.run_id,
            "n_baseline_cells": int(len(result.baseline_long)),
            "n_excluded": int(len(result.excluded)),
            "n_alignment_cells": int(len(result.alignment_table)),
            "output_files": result.output_files,
            "warnings": result.warnings,
            "dry_run": bool(args.dry_run),
        }
        print(json.dumps(summary, indent=2, default=str))
        return 0
    raise SystemExit(f"Unknown baseline command: {cmd}")
