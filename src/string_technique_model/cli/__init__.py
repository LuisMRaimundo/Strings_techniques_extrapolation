"""Command-line interface for string-technique-model."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from string_technique_model.cli.assumptions import register_assumptions_parser, run_assumptions_command
from string_technique_model.cli.baseline import register_baseline_parser, run_baseline_command
from string_technique_model.cli.extrapolation import (
    register_extrapolation_parser,
    run_extrapolation_command,
    run_request_command,
)
from string_technique_model.cli.literature import register_literature_parser, run_literature_command
from string_technique_model.cli.nonlinear import register_nonlinear_parser, run_nonlinear_command
from string_technique_model.cli.prediction import register_prediction_parser, run_prediction_command


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="string-technique-model",
        description="Literature-informed bowed-string technique density estimation",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run estimation pipeline (later phases)")
    run_p.add_argument("--config", type=Path, default=None)
    run_p.add_argument("--instruments", nargs="+", default=None)
    run_p.add_argument("--techniques", nargs="+", default=None)
    run_p.add_argument("--baseline-collections", nargs="+", default=None)
    run_p.add_argument("--pooling-method", default=None)

    est_p = sub.add_parser("estimate", help="Estimate using selected baseline collections")
    est_p.add_argument("--config", type=Path, default=None)
    est_p.add_argument("--baseline-collections", nargs="+", required=True)
    est_p.add_argument("--techniques", nargs="+", default=None)
    est_p.add_argument("--instruments", nargs="+", default=None)
    est_p.add_argument("--pooling-method", default=None)

    look_p = sub.add_parser("lookup", help="Lookup one cell (later phases)")
    look_p.add_argument("--instrument", required=True)
    look_p.add_argument("--technique", required=True)
    look_p.add_argument("--note", required=True)
    look_p.add_argument("--dynamic", required=True, choices=["pp", "mf", "ff"])
    look_p.add_argument("--baseline-collections", nargs="+", default=None)
    look_p.add_argument("--config", type=Path, default=None)

    sub.add_parser(
        "gui",
        help="Launch numerical narrow extrapolator GUI (no audio)",
    )

    coll = sub.add_parser("collection", help="Collection registry and ingestion commands")
    coll_sub = coll.add_subparsers(dest="collection_command", required=True)

    reg_p = coll_sub.add_parser("register", help="Register a collection in the YAML registry")
    reg_p.add_argument("--collection-id", required=True)
    reg_p.add_argument("--config", type=Path, default=Path("configs/collections.yaml"))
    reg_p.add_argument("--display-name", default=None)
    reg_p.add_argument(
        "--data-path",
        action="append",
        dest="data_paths",
        default=None,
        help="Source data path (repeatable)",
    )
    reg_p.add_argument("--format", default="csv")
    reg_p.add_argument("--schema-mapping", default=None)
    reg_p.add_argument("--metric-definition-id", default="ewsd_v1")
    reg_p.add_argument("--default-role", action="append", dest="default_roles", default=None)
    reg_p.add_argument("--notes", default=None)
    reg_p.add_argument("--dry-run", action="store_true")

    for name, help_text in [
        ("inspect", "Inspect a registered collection"),
        ("validate", "Validate schema and metric compatibility"),
        ("import", "Import a collection to canonical parquet + reports"),
    ]:
        p = coll_sub.add_parser(name, help=help_text)
        p.add_argument("--collection-id", required=True)
        p.add_argument("--config", type=Path, default=None)
        if name == "import":
            p.add_argument("--dry-run", action="store_true")
            p.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=True)
            p.add_argument(
                "--include-invalid-records",
                action="store_true",
                help="Debug: keep unsupported-instrument rows in the canonical parquet",
            )

    list_p = coll_sub.add_parser("list", help="List registered collections")
    list_p.add_argument("--config", type=Path, default=None)

    cmp = coll_sub.add_parser("compare", help="Compare metric compatibility across collections")
    cmp.add_argument("--collection-ids", nargs="+", required=True)
    cmp.add_argument("--config", type=Path, default=None)

    register_baseline_parser(sub)
    register_literature_parser(sub)
    register_prediction_parser(sub)
    register_assumptions_parser(sub)
    register_extrapolation_parser(sub)
    register_nonlinear_parser(sub)

    stress = sub.add_parser("stress-test", help="Scientific acoustics stress testing")
    stress_sub = stress.add_subparsers(dest="stress_command", required=True)
    acoustics = stress_sub.add_parser("acoustics", help="Run acoustics stress suite and write reports")
    acoustics.add_argument("--tier", choices=["fast", "extended", "benchmark", "all"], default="fast")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(bool(getattr(args, "verbose", False)))

    try:
        if args.command == "gui":
            from string_technique_model.gui import launch_gui

            launch_gui()
            return 0

        if args.command in {"run", "estimate"}:
            from string_technique_model.pipeline import run_pipeline

            summary = run_pipeline(
                args.config,
                instruments=args.instruments,
                techniques=args.techniques,
                baseline_collection_ids=getattr(args, "baseline_collections", None),
                pooling_method=getattr(args, "pooling_method", None),
                progress=lambda msg: print(msg, flush=True),
            )
            print(json.dumps({k: v for k, v in summary.items() if not k.endswith("_rows")}, indent=2))
            return 0

        if args.command == "lookup":
            from string_technique_model.pipeline import lookup_single

            result = lookup_single(
                args.instrument,
                args.technique,
                args.note,
                args.dynamic,
                run_config_path=args.config,
                baseline_collection_ids=args.baseline_collections,
            )
            print(json.dumps(result, indent=2))
            return 0

        if args.command == "collection":
            return _collection_command(args)

        if args.command == "baseline":
            return run_baseline_command(args)

        if args.command == "literature":
            return run_literature_command(args)

        if args.command == "predict":
            return run_prediction_command(args)
        if args.command == "assumptions":
            return run_assumptions_command(args)
        if args.command == "extrapolate":
            return run_extrapolation_command(args)
        if args.command == "request":
            return run_request_command(args)
        if args.command == "nonlinear":
            return run_nonlinear_command(args)

        if args.command == "stress-test":
            from string_technique_model.testing.stress_runner import run_acoustics_stress

            if args.stress_command == "acoustics":
                return run_acoustics_stress(tier=str(args.tier))
            parser.error(f"Unknown stress-test command: {args.stress_command}")
            return 2

        parser.error(f"Unknown command: {args.command}")
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        logging.getLogger("string_technique_model.cli").error("%s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _collection_command(args: argparse.Namespace) -> int:
    from string_technique_model.collections import service

    cmd = args.collection_command
    if cmd == "list":
        print(json.dumps(service.list_collections(args.config), indent=2))
        return 0
    if cmd == "inspect":
        print(json.dumps(service.inspect_collection(args.collection_id, args.config), indent=2))
        return 0
    if cmd == "validate":
        payload = service.validate_collection(args.collection_id, args.config)
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("schema", {}).get("ok", False) else 1
    if cmd == "import":
        result = service.import_collection(
            args.collection_id,
            args.config,
            dry_run=bool(getattr(args, "dry_run", False)),
            overwrite=bool(getattr(args, "overwrite", True)),
            include_invalid_records=bool(getattr(args, "include_invalid_records", False)),
        )
        print(json.dumps(result, indent=2))
        return 0
    if cmd == "compare":
        print(
            json.dumps(
                service.compare_collections(args.collection_ids, args.config),
                indent=2,
            )
        )
        return 0
    if cmd == "register":
        entry = service.register_collection(
            args.collection_id,
            config_path=args.config,
            display_name=args.display_name,
            data_paths=args.data_paths,
            fmt=args.format,
            schema_mapping=args.schema_mapping,
            metric_definition_id=args.metric_definition_id,
            default_roles=args.default_roles,
            notes=args.notes,
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(entry, indent=2))
        return 0
    raise SystemExit(f"Unknown collection command: {cmd}")


__all__ = ["build_parser", "main"]
