"""CLI for the narrow literature extrapolator and note-level requests.

Also exposes Phase-1 nonlinear commands as::

    python -m string_technique_model extrapolate fit-baseline ...
    python -m string_technique_model extrapolate fit-technique ...
    python -m string_technique_model extrapolate predict ...
    python -m string_technique_model extrapolate compare ...
    python -m string_technique_model extrapolate diagnose ...
    python -m string_technique_model extrapolate export ...

Legacy grid extrapolator remains available as::

    python -m string_technique_model extrapolate grid ...
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from string_technique_model.config import PACKAGE_ROOT


def register_extrapolation_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "extrapolate",
        help="Literature / nonlinear extrapolation (grid legacy + hierarchical Phase 1)",
    )
    nest = p.add_subparsers(dest="extrapolate_command", required=True)

    grid = nest.add_parser("grid", help="Legacy narrow literature grid extrapolator")
    grid.add_argument("--evidence", type=Path, default=None)
    grid.add_argument("--targets", type=Path, default=None)
    grid.add_argument("--baseline-dir", type=Path, default=None)
    grid.add_argument("--research-excel", type=Path, default=None)
    grid.add_argument("--orchidea-root", type=Path, default=None)
    grid.add_argument("--orchidea-manifest", type=Path, default=None)
    grid.add_argument("--no-orchidea-manifest", action="store_true")
    grid.add_argument("--output", type=Path, default=None)

    fb = nest.add_parser("fit-baseline", help="Fit ordinary baseline splines (M1 Phase 1)")
    fb.add_argument("--instrument", default=None)
    fb.add_argument("--dynamic", default=None)
    fb.add_argument("--quantity", default="EWSD_score_acoustic_balanced")
    fb.add_argument("--research-excel", type=Path, default=None)
    fb.add_argument("--orchidea-root", type=Path, default=None)

    ft = nest.add_parser("fit-technique", help="Fit technique submodel (bow/mute)")
    ft.add_argument("--technique", required=True)
    ft.add_argument("--instrument", required=True)
    ft.add_argument("--dynamic", default="pp")
    ft.add_argument("--model", default="hierarchical-spline")
    ft.add_argument("--research-excel", type=Path, default=None)
    ft.add_argument("--orchidea-root", type=Path, default=None)

    pr = nest.add_parser("predict", help="Predict technique register (nonlinear)")
    pr.add_argument("--technique", required=True)
    pr.add_argument("--instrument", required=True)
    pr.add_argument("--dynamic", default="pp")
    pr.add_argument(
        "--method",
        default="hierarchical_spline",
        choices=["constant", "hierarchical_spline", "physical_informed_bayesian", "evidence_only"],
    )
    pr.add_argument("--mode", default=None, help="Alias for --method (compat)")
    pr.add_argument("--quantity", default="EWSD_score_acoustic_balanced")
    pr.add_argument("--research-excel", type=Path, default=None)
    pr.add_argument("--orchidea-root", type=Path, default=None)
    pr.add_argument(
        "--export-xlsx",
        type=Path,
        default=PACKAGE_ROOT / "outputs" / "nonlinear_extrapolation_results.xlsx",
    )

    cmp_ = nest.add_parser("compare", help="Compare M0 constant vs M1 hierarchical spline")
    cmp_.add_argument("--technique", required=True)
    cmp_.add_argument("--instrument", required=True)
    cmp_.add_argument("--dynamic", default="pp")
    cmp_.add_argument("--research-excel", type=Path, default=None)
    cmp_.add_argument("--orchidea-root", type=Path, default=None)

    nest.add_parser("diagnose", help="Backend capability diagnostics")

    ex = nest.add_parser("export", help="Alias of predict with Excel export")
    ex.add_argument("--technique", required=True)
    ex.add_argument("--instrument", required=True)
    ex.add_argument("--dynamic", default="pp")
    ex.add_argument(
        "--method",
        default="hierarchical_spline",
        choices=["constant", "hierarchical_spline", "physical_informed_bayesian", "evidence_only"],
    )
    ex.add_argument("--quantity", default="EWSD_score_acoustic_balanced")
    ex.add_argument("--research-excel", type=Path, default=None)
    ex.add_argument("--orchidea-root", type=Path, default=None)
    ex.add_argument(
        "--export-xlsx",
        type=Path,
        default=PACKAGE_ROOT / "outputs" / "nonlinear_extrapolation_results.xlsx",
    )

    r = sub.add_parser(
        "request",
        help="Note-level requests: Measured notes → needed notes + technique",
    )
    r.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Excel with sheets Measured + Requests (note/value + note/technique)",
    )
    r.add_argument(
        "--research-excel",
        type=Path,
        default=None,
        help="Use Spectral_Analyser research Excel as Measured registry",
    )
    r.add_argument("--requests", type=Path, default=None, help="Optional separate Requests Excel/CSV")
    r.add_argument("--instrument", type=str, default=None, help="Default instrument if missing in columns")
    r.add_argument("--dynamic", type=str, default=None, help="Default dynamic if missing in columns")
    r.add_argument("--evidence", type=Path, default=None)
    r.add_argument(
        "--write-template",
        type=Path,
        default=None,
        help="Write Measured/Requests template Excel and exit",
    )
    r.add_argument("--output", type=Path, default=None)


def run_extrapolation_command(args: argparse.Namespace) -> int:
    cmd = getattr(args, "extrapolate_command", None)
    if cmd == "grid":
        from string_technique_model.extrapolation.engine import run_narrow_extrapolation
        from string_technique_model.extrapolation.export import export_extrapolation_workbook

        result = run_narrow_extrapolation(
            evidence_path=args.evidence,
            target_path=args.targets,
            baseline_dir=args.baseline_dir,
            research_excel=args.research_excel,
            orchidea_root=args.orchidea_root,
            orchidea_manifest=args.orchidea_manifest,
            use_orchidea_manifest=not args.no_orchidea_manifest,
        )
        out = args.output or (
            PACKAGE_ROOT / "outputs" / "extrapolation" / "narrow_priority1_extrapolation.xlsx"
        )
        path = export_extrapolation_workbook(result, out)
        print(json.dumps({"output": str(path), "summary": result["summary"]}, indent=2))
        return 0

    # Delegate Phase-1 nonlinear commands
    from string_technique_model.cli.nonlinear import run_nonlinear_command

    if cmd == "export":
        args.nonlinear_command = "predict"
    elif cmd in {"fit-baseline", "fit-technique", "predict", "compare", "diagnose"}:
        args.nonlinear_command = cmd
    else:
        print(json.dumps({"error": "unknown_extrapolate_command", "command": cmd}, indent=2))
        return 2

    if getattr(args, "mode", None) and not getattr(args, "method", None):
        args.method = str(args.mode).replace("-", "_")
    elif getattr(args, "mode", None):
        # Prefer explicit --method; mode is alias when provided alone
        pass

    return run_nonlinear_command(args)


def run_request_command(args: argparse.Namespace) -> int:
    from string_technique_model.extrapolation.note_level import (
        export_note_level_workbook,
        measured_from_research_excel,
        run_from_workbook,
        run_note_level_requests,
    )
    from string_technique_model.extrapolation.request_io import parse_request_table, write_request_template

    if args.write_template:
        path = write_request_template(args.write_template)
        print(json.dumps({"template": str(path)}, indent=2))
        return 0

    if args.workbook:
        result = run_from_workbook(
            args.workbook,
            default_instrument=args.instrument,
            default_dynamic=args.dynamic,
            evidence_path=args.evidence,
        )
        out = args.output or (PACKAGE_ROOT / "outputs" / "extrapolation" / "note_level_requests.xlsx")
        path = export_note_level_workbook(result, out)
        print(
            json.dumps(
                {
                    "output": str(path),
                    "summary": result["summary"],
                    "load_warnings": result.get("load_warnings"),
                },
                indent=2,
            )
        )
        return 0

    measured: list = []
    requests: list = []
    warnings: list[str] = []

    if args.research_excel:
        measured, w = measured_from_research_excel(
            args.research_excel,
            instrument=args.instrument,
            dynamic=args.dynamic,
        )
        warnings.extend(w)

    if args.requests:
        import pandas as pd

        frame = (
            pd.read_excel(args.requests)
            if str(args.requests).endswith(".xlsx")
            else pd.read_csv(args.requests)
        )
        requests, w = parse_request_table(
            frame,
            default_instrument=args.instrument,
            default_dynamic=args.dynamic,
        )
        warnings.extend(w)

    if not measured or not requests:
        print(
            json.dumps(
                {
                    "error": (
                        "Need Measured rows and Request rows. Use --workbook, "
                        "or --research-excel plus --requests, or --write-template."
                    ),
                    "warnings": warnings,
                },
                indent=2,
            )
        )
        return 2

    for req in requests:
        req["instrument"] = req.get("instrument") or args.instrument
        req["dynamic"] = req.get("dynamic") or args.dynamic

    result = run_note_level_requests(measured, requests, evidence_path=args.evidence)
    out = args.output or (PACKAGE_ROOT / "outputs" / "extrapolation" / "note_level_requests.xlsx")
    path = export_note_level_workbook(result, out)
    print(json.dumps({"output": str(path), "summary": result["summary"], "warnings": warnings}, indent=2))
    return 0
