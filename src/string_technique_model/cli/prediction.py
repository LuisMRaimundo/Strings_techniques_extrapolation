"""CLI for evidence-gated technique predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def register_prediction_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    pred = subparsers.add_parser("predict", help="Evidence-gated technique prediction (Phase 4)")
    sub = pred.add_subparsers(dest="predict_command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true")
    common.add_argument("--strict", action="store_true")
    common.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=True)
    common.add_argument("--output-dir", type=Path, default=None)
    common.add_argument("--seed", type=int, default=None)
    common.add_argument("--n-draws", type=int, default=None)
    common.add_argument("--instrument", "--instruments", nargs="+", dest="instruments", default=None)
    common.add_argument("--technique", "--techniques", nargs="+", dest="techniques", default=None)
    common.add_argument("--dynamic", nargs="+", default=None)
    common.add_argument("--pitch-min", type=float, default=None)
    common.add_argument("--pitch-max", type=float, default=None)
    common.add_argument("--allow-transfer", action="store_true")
    common.add_argument(
        "--mode",
        choices=["evidence-only", "evidence-plus-user-assumptions"],
        default="evidence-only",
        help="Prediction input mode; defaults to evidence-only.",
    )

    build = sub.add_parser("build", parents=[common], help="Build technique predictions")
    build.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Ordinary baseline long table (.parquet or .csv)",
    )
    build.add_argument(
        "--backend",
        choices=["metric-only", "spectrum-aware"],
        default="metric-only",
    )
    build.add_argument(
        "--activate-user-assumptions",
        action="store_true",
        help=(
            "Explicitly activate user numerical assumptions for this run. "
            "Results are labelled assumption-based, never literature-validated."
        ),
    )

    from_ord = sub.add_parser(
        "from-ordinary",
        help=(
            "Forecast techniques from ordinary data (CDM JSON or baseline table). "
            "Default: qualitative + NA. Use --activate-user-assumptions for "
            "assumption-based numbers only."
        ),
    )
    from_ord.add_argument("--instrument", required=True, help="vln|vla|vlc|cb or name")
    from_ord.add_argument("--dynamic", default="mf")
    from_ord.add_argument("--technique", "--techniques", nargs="+", dest="techniques", default=None)
    from_ord.add_argument("--output-dir", type=Path, default=None)
    from_ord.add_argument("--seed", type=int, default=None)
    from_ord.add_argument("--n-draws", type=int, default=None)
    from_ord.add_argument("--dry-run", action="store_true")
    from_ord.add_argument(
        "--mode",
        choices=["evidence-only", "evidence-plus-user-assumptions"],
        default="evidence-only",
        help="Prediction input mode; defaults to evidence-only.",
    )
    from_ord.add_argument(
        "--source-json",
        type=Path,
        default=None,
        help="Ordinary CDM JSON (default: data/baselines/<instrument>_ordinary_cdm.json)",
    )
    from_ord.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Optional existing ordinary baseline long table (.csv/.parquet)",
    )
    from_ord.add_argument(
        "--activate-user-assumptions",
        action="store_true",
        help=(
            "Explicitly activate user numerical assumptions. "
            "Each assumption must also have active_for_density_prediction: true."
        ),
    )

    val = sub.add_parser("validate-context", help="Validate prediction request contexts")
    val.add_argument("--requests", type=Path, required=True)

    insp = sub.add_parser("inspect-parameters", help="Inspect activation for one cell")
    insp.add_argument("--instrument", required=True)
    insp.add_argument("--technique", required=True)
    insp.add_argument("--dynamic", default="mf")
    insp.add_argument("--mute-type", default=None)
    insp.add_argument("--harmonic-order", type=int, default=None)
    insp.add_argument("--allow-transfer", action="store_true")

    expl = sub.add_parser("explain", help="Explain a prediction_id from outputs")
    expl.add_argument("--prediction-id", required=True)
    expl.add_argument(
        "--predictions",
        type=Path,
        default=Path("outputs/predictions/technique_predictions.csv"),
    )
    expl.add_argument(
        "--ledger",
        type=Path,
        default=Path("outputs/predictions/prediction_parameter_ledger.csv"),
    )

    sens = sub.add_parser("sensitivity", parents=[common], help="Run sensitivity scaffolding")
    sens.add_argument("--baseline-density", type=float, default=20.0)

    sub.add_parser("validation-status", help="Report whether external validation has run")


def run_prediction_command(args: argparse.Namespace) -> int:
    cmd = args.predict_command
    mode = (
        "evidence_plus_user_assumptions"
        if bool(getattr(args, "activate_user_assumptions", False))
        or getattr(args, "mode", "evidence-only") == "evidence-plus-user-assumptions"
        else "evidence_only"
    )
    if cmd == "build":
        import pandas as pd

        from string_technique_model.prediction.pipeline import build_predictions
        from string_technique_model.sensitivity.prediction_sensitivity import (
            run_prediction_sensitivity,
        )
        from string_technique_model.validation.prediction_validation import (
            run_prediction_validation,
        )

        result = build_predictions(
            baseline_path=args.baseline,
            instruments=args.instruments,
            techniques=args.techniques,
            backend=args.backend,
            output_dir=args.output_dir,
            n_draws=args.n_draws,
            random_seed=args.seed,
            allow_transfer=bool(args.allow_transfer),
            dry_run=bool(args.dry_run),
            overwrite=bool(args.overwrite),
            strict=bool(args.strict),
            dynamic=args.dynamic,
            pitch_min=args.pitch_min,
            pitch_max=args.pitch_max,
            mode=mode,
            activate_user_assumptions=bool(args.activate_user_assumptions),
        )
        # Sensitivity / validation scaffolding (does not invent coefficients)
        run_prediction_sensitivity(baseline={"baseline_value": 20.0}, active_parameters=[])
        run_prediction_validation(pd.DataFrame(result.rows), observations=None)
        print(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "n_rows": len(result.rows),
                    "n_numerical": sum(
                        1 for r in result.rows if r.get("estimated_density_mean") is not None
                    ),
                    "n_na": sum(1 for r in result.rows if r.get("estimated_density_mean") is None),
                    "n_active_parameters_global": result.n_active_parameters_global,
                    "n_inactive_parameters_global": result.n_inactive_parameters_global,
                    "activation_failure_reasons": result.activation_failure_reasons,
                    "output_files": result.output_files,
                    "measured_status_used": False,
                    "transfer_default": False,
                },
                indent=2,
                default=str,
            )
        )
        return 0

    if cmd == "from-ordinary":
        from string_technique_model.prediction.from_ordinary import predict_from_ordinary

        result = predict_from_ordinary(
            instrument=args.instrument,
            dynamic=str(args.dynamic),
            techniques=args.techniques,
            source_json=args.source_json,
            baseline_path=args.baseline,
            output_dir=args.output_dir,
            mode=mode,
            activate_user_assumptions=bool(getattr(args, "activate_user_assumptions", False)),
            n_draws=args.n_draws,
            random_seed=args.seed,
            dry_run=bool(args.dry_run),
        )
        n_assumption = sum(
            1
            for r in result.prediction.rows
            if r.get("result_basis") == "user_assumption"
            and r.get("estimated_density_mean") is not None
        )
        print(
            json.dumps(
                {
                    "activation_mode": result.activation_mode,
                    "baseline_path": result.baseline_path,
                    "n_rows": len(result.prediction.rows),
                    "n_numerical_evidence_based": sum(
                        1
                        for r in result.prediction.rows
                        if r.get("evidence_based") and r.get("estimated_density_mean") is not None
                    ),
                    "n_numerical_assumption_based": n_assumption,
                    "n_na": sum(
                        1
                        for r in result.prediction.rows
                        if r.get("estimated_density_mean") is None
                    ),
                    "n_qualitative_rows": len(result.qualitative_rows),
                    "warnings": result.warnings,
                    "output_files": result.output_files,
                    "label_notice": (
                        "Assumption-based rows are NOT literature-validated and NOT evidence-based."
                        if n_assumption
                        else "No assumption-based numerical estimates in this run."
                    ),
                },
                indent=2,
                default=str,
            )
        )
        return 0

    if cmd == "validate-context":
        from string_technique_model.models.registry import get_model
        from string_technique_model.prediction.requests import load_prediction_requests

        requests = load_prediction_requests(args.requests)
        payload = []
        for req in requests:
            model = get_model(req.instrument, req.target_technique)
            result = model.validate_context(None, req.to_context())
            payload.append(
                {
                    "instrument": req.instrument,
                    "technique": req.target_technique,
                    "ok": result.ok,
                    "status": result.status,
                    "missing_required": result.missing_required,
                }
            )
        print(json.dumps(payload, indent=2))
        return 0

    if cmd == "inspect-parameters":
        from string_technique_model.literature.extracts import load_extracts
        from string_technique_model.literature.parameter_ledger import load_parameter_config
        from string_technique_model.literature.source_registry import SourceRegistry
        from string_technique_model.prediction.activation import resolve_prediction_parameters

        records = resolve_prediction_parameters(
            list(load_parameter_config().get("parameters") or []),
            registry=SourceRegistry.from_yaml(),
            extracts=load_extracts(),
            context={
                "instrument": args.instrument,
                "technique": args.technique,
                "dynamic": args.dynamic,
                "mute_type": args.mute_type,
                "harmonic_order": args.harmonic_order,
                "harmonic_type": "artificial"
                if args.technique == "artificial_harmonic"
                else None,
                "target_metric_definition_id": "ewsd_v1",
            },
            backend="metric-only",
            transfers_enabled=bool(args.allow_transfer),
        )
        print(
            json.dumps(
                [
                    {
                        "parameter_id": r.parameter_id,
                        "status": r.status,
                        "reasons": r.reasons,
                    }
                    for r in records
                ],
                indent=2,
            )
        )
        return 0

    if cmd == "explain":
        import pandas as pd

        preds = pd.read_csv(args.predictions)
        ledger = pd.read_csv(args.ledger)
        row = preds[preds["prediction_id"] == args.prediction_id]
        led = ledger[ledger["prediction_id"] == args.prediction_id]
        print(
            json.dumps(
                {
                    "prediction": row.to_dict(orient="records"),
                    "parameter_ledger": led.to_dict(orient="records"),
                },
                indent=2,
                default=str,
            )
        )
        return 0 if not row.empty else 1

    if cmd == "sensitivity":
        from string_technique_model.sensitivity.prediction_sensitivity import (
            run_prediction_sensitivity,
        )

        payload = run_prediction_sensitivity(
            baseline={"baseline_value": float(args.baseline_density)},
            active_parameters=[],
        )
        print(json.dumps(payload, indent=2))
        return 0

    if cmd == "validation-status":
        from string_technique_model.validation.prediction_validation import validation_enabled

        print(
            json.dumps(
                {
                    "validation_enabled": validation_enabled(),
                    "claim": "External validation has not been claimed unless a report says it was run.",
                },
                indent=2,
            )
        )
        return 0

    raise ValueError(f"Unknown predict command: {cmd}")
