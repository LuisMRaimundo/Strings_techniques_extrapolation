"""CLI for nonlinear hierarchical extrapolation (Phase 1)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT


def register_nonlinear_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "nonlinear",
        help="Nonlinear hierarchical extrapolation (baseline, M1 spline, optional Bayes)",
    )
    nest = p.add_subparsers(dest="nonlinear_command", required=True)

    fb = nest.add_parser("fit-baseline", help="Fit ordinary baseline splines")
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

    pr = nest.add_parser("predict", help="Predict technique register")
    pr.add_argument("--technique", required=True)
    pr.add_argument("--instrument", required=True)
    pr.add_argument("--dynamic", default="pp")
    pr.add_argument(
        "--method",
        default="hierarchical_spline",
        choices=["constant", "hierarchical_spline", "physical_informed_bayesian", "evidence_only"],
    )
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


def _df_to_ordinary_dicts(df) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        rows.append(
            {
                "note": r.get("note"),
                "value": r.get("value"),
                "instrument": r.get("instrument"),
                "dynamic": r.get("dynamic"),
                "technique": "ordinary",
                "quantity": r.get("quantity") or "EWSD_score_acoustic_balanced",
                "midi": r.get("midi"),
                "source_path": r.get("source_path"),
            }
        )
    return rows


def _load_ordinary_df(research_excel: Path | None, orchidea_root: Path | None, instrument: str | None, dynamic: str | None):
    from string_technique_model.extrapolation.nonlinear.data_preparation import (
        filter_ordinary,
        load_measured_from_orchidea_manifest,
        load_measured_from_workbook,
    )

    warnings: list[str] = []
    if research_excel:
        df, w = load_measured_from_workbook(research_excel)
        warnings.extend(w)
    else:
        df, w = load_measured_from_orchidea_manifest(orchidea_root=orchidea_root)
        warnings.extend(w)
    df = filter_ordinary(df)
    if instrument:
        df = df[df["instrument"].astype(str) == str(instrument)]
    if dynamic:
        df = df[df["dynamic"].astype(str) == str(dynamic)]
    return df, warnings


def run_nonlinear_command(args: argparse.Namespace) -> int:
    cmd = args.nonlinear_command
    if cmd == "diagnose":
        from dataclasses import asdict

        from string_technique_model.extrapolation.nonlinear import check_backend
        from string_technique_model.extrapolation.nonlinear.descriptor_model import ewsd_mapping_status

        status = check_backend()
        payload = asdict(status)
        payload["ewsd_mapping_status"] = ewsd_mapping_status("EWSD_score_acoustic_balanced")
        print(json.dumps(payload, indent=2))
        return 0

    if cmd == "fit-baseline":
        from string_technique_model.extrapolation.nonlinear import fit_ordinary_baseline

        df, warnings = _load_ordinary_df(
            args.research_excel, getattr(args, "orchidea_root", None), args.instrument, args.dynamic
        )
        if df.empty:
            print(json.dumps({"error": "no_ordinary_rows", "warnings": warnings}, indent=2))
            return 2
        fits = fit_ordinary_baseline(df)
        keys = [f"{k[0]}|{k[1]}" for k in fits.fits]
        print(
            json.dumps(
                {"n_baseline_cells": len(keys), "cells": keys, "n_rows": int(len(df)), "warnings": warnings[-5:]},
                indent=2,
            )
        )
        return 0

    if cmd == "fit-technique":
        from string_technique_model.extrapolation.nonlinear import fit_ordinary_baseline, fit_technique_effect

        df, warnings = _load_ordinary_df(
            args.research_excel, getattr(args, "orchidea_root", None), args.instrument, args.dynamic
        )
        if df.empty:
            print(json.dumps({"error": "missing_baseline", "warnings": warnings}, indent=2))
            return 2
        baseline = fit_ordinary_baseline(df)
        effect = fit_technique_effect(
            baseline,
            None,
            technique=args.technique,
            instrument=args.instrument,
            dynamic=args.dynamic,
        )
        print(
            json.dumps(
                {
                    "technique": args.technique,
                    "instrument": args.instrument,
                    "dynamic": args.dynamic,
                    "model": args.model,
                    "effect_type": type(effect).__name__,
                    "prior_dominated": bool(getattr(effect, "prior_dominated", None)),
                    "evidence_tier": str(getattr(effect, "evidence_tier", None)),
                },
                indent=2,
                default=str,
            )
        )
        return 0

    if cmd == "predict":
        from string_technique_model.extrapolation.nonlinear import export_nonlinear_workbook, predict_register

        df, warnings = _load_ordinary_df(
            args.research_excel, args.orchidea_root, args.instrument, args.dynamic
        )
        rows = _df_to_ordinary_dicts(df)
        if not rows:
            print(json.dumps({"error": "missing_baseline", "warnings": warnings}, indent=2))
            return 2
        results = predict_register(
            rows,
            technique=args.technique,
            instrument=args.instrument,
            dynamic=args.dynamic,
            method=args.method,
            target_quantity=args.quantity,
        )
        out = export_nonlinear_workbook(
            results,
            args.export_xlsx,
            run_metadata={
                "requested_method": "automatic"
                if args.method == "hierarchical_spline"
                else args.method,
                "cli_method_control": args.method,
                "load_warnings": warnings[-5:],
            },
        )
        n_num = sum(1 for r in results if r.posterior_median is not None or r.posterior_mean is not None)
        print(
            json.dumps(
                {
                    "output": str(out),
                    "n_results": len(results),
                    "n_numeric": n_num,
                    "method": args.method,
                    "warnings": warnings[-5:],
                },
                indent=2,
            )
        )
        return 0

    if cmd == "compare":
        from string_technique_model.extrapolation.nonlinear import compare_models

        df, warnings = _load_ordinary_df(
            args.research_excel, getattr(args, "orchidea_root", None), args.instrument, args.dynamic
        )
        rows = _df_to_ordinary_dicts(df)
        cmp_res = compare_models(
            rows,
            technique=args.technique,
            instrument=args.instrument,
            dynamic=args.dynamic,
        )
        payload = cmp_res.model_dump() if hasattr(cmp_res, "model_dump") else cmp_res
        print(json.dumps(payload, indent=2, default=str))
        return 0

    return 2
