from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from string_technique_model.baselines import (
    build_baseline_table,
    lookup_pooled_density,
    resolve_run_collections,
)
from string_technique_model.collections.service import load_imported_or_ingest
from string_technique_model.config import PACKAGE_ROOT, load_run_config, load_yaml
from string_technique_model.data_io import TECHNIQUE_DISPLAY, normalize_instrument
from string_technique_model.density.metric import load_density_metric
from string_technique_model.estimate import compare_to_holdout, estimate_cell
from string_technique_model.provenance import validate_all_parameters
from string_technique_model.stable_seed import stable_seed

ProgressCallback = Callable[[str], None]


def _emit(cb: ProgressCallback | None, message: str) -> None:
    if cb:
        cb(message)


def run_pipeline(
    run_config_path: Path | str | None = None,
    *,
    instruments: list[str] | None = None,
    techniques: list[str] | None = None,
    baseline_collection_ids: list[str] | None = None,
    pooling_method: str | None = None,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    cfg = load_run_config(run_config_path)
    paths = cfg["paths_resolved"]
    run_resolved = resolve_run_collections(cfg)
    if baseline_collection_ids:
        cfg.setdefault("run", {})["baseline_collection_ids"] = list(baseline_collection_ids)
    if pooling_method:
        cfg.setdefault("run", {}).setdefault("pooling", {})["method"] = pooling_method
        cfg["run"]["pooling"]["enabled"] = True

    instruments = instruments or list(cfg.get("instruments") or ["vln", "vla", "vlc", "cb"])
    techniques = techniques or list(
        cfg.get("techniques")
        or ["artificial_harmonic", "sul_ponticello", "sul_tasto", "con_sordino"]
    )

    _emit(progress, "Loading literature parameters...")
    lit_path = Path(paths["literature_parameters"])
    lit = load_yaml(lit_path)
    # Relational provenance: inactive/indirect candidates must not crash the pipeline.
    provenance_report = validate_all_parameters(lit_path, strict=False)
    parameters = provenance_report.get("parameters") or lit.get("parameters") or []
    unsupported = lit.get("unsupported_requested_parameters") or []
    if provenance_report.get("inactive_failures"):
        _emit(
            progress,
            f"Inactive/indirect provenance notes: {len(provenance_report['inactive_failures'])}",
        )
    metric = load_density_metric(paths["density_metric"])

    _emit(progress, "Building multi-collection baselines...")
    pooled_df, baseline_prov = build_baseline_table(
        cfg,
        baseline_collection_ids=baseline_collection_ids,
        run_config_path=run_config_path,
    )

    validation_ids = run_resolved["validation_collection_ids"]
    validation_df = (
        load_imported_or_ingest(validation_ids, run_config_path) if validation_ids else pd.DataFrame()
    )

    n_draws = int(cfg.get("n_draws", 5000))
    seed = int(cfg.get("random_seed", 0))
    estimate_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []

    notes = sorted(
        {
            str(n)
            for n in pooled_df.get("pitch_name_sounding", pd.Series(dtype=str)).dropna().unique()
        }
    )

    for code in instruments:
        _emit(progress, f"Estimating instrument={code}...")
        for technique in techniques:
            for note in notes:
                for dynamic in ("pp", "mf", "ff"):
                    hit = lookup_pooled_density(
                        pooled_df,
                        instrument=code,
                        note=note,
                        dynamic=dynamic,
                    )
                    prov = {
                        **baseline_prov,
                        **(hit or {}),
                        "target_metric_definition_id": baseline_prov.get(
                            "target_metric_definition_id"
                        ),
                    }
                    ordinary = None if hit is None else hit.get("ordinary_density")
                    result = estimate_cell(
                        instrument=code,
                        technique=technique,
                        note=note,
                        dynamic=dynamic,
                        ordinary_density=ordinary,
                        parameters=parameters,
                        n_draws=n_draws,
                        random_seed=seed + stable_seed(code, technique, note, dynamic),
                        metric=metric,
                        unsupported_reasons=unsupported,
                        baseline_provenance=prov,
                    )
                    row = result.to_dict()
                    estimate_rows.append(row)

                    if not validation_df.empty:
                        measured = _lookup_validation(
                            validation_df, code, technique, note, dynamic
                        )
                        cmp = compare_to_holdout(result, measured)
                        comparison_rows.append({**row, **cmp})

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(paths["outputs_dir"]) / f"run_{stamp}"
    reports_dir = Path(paths["reports_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    _emit(progress, f"Writing outputs to {out_dir}...")
    est_df = pd.DataFrame(estimate_rows)
    est_path = out_dir / "technique_estimates.csv"
    pooled_path = out_dir / "pooled_baselines.csv"
    est_df.to_csv(est_path, index=False)
    pooled_df.to_csv(pooled_path, index=False)

    summary = {
        "timestamp_utc": stamp,
        "model_version": cfg.get("model_version"),
        "literature_parameter_version": cfg.get("literature_parameter_version"),
        "instruments": instruments,
        "techniques": techniques,
        "baseline_collection_ids": list(
            baseline_collection_ids or baseline_prov.get("baseline_collection_ids") or []
        ),
        "n_contributing_collections_configured": len(
            baseline_collection_ids or baseline_prov.get("baseline_collection_ids") or []
        ),
        "pooling_method": baseline_prov.get("pooling_method"),
        "n_estimate_rows": len(estimate_rows),
        "n_estimated": int((est_df["estimation_status"] == "estimated").sum()) if len(est_df) else 0,
        "n_not_estimable": int(
            (est_df["estimation_status"] == "not_estimable_from_current_evidence").sum()
        )
        if len(est_df)
        else 0,
        "n_literature_parameters": len(parameters),
        "density_metric": metric.name,
        "target_metric_definition_id": baseline_prov.get("target_metric_definition_id"),
        "outputs": {
            "estimates_csv": str(est_path),
            "pooled_baselines_csv": str(pooled_path),
            "run_dir": str(out_dir),
        },
        "baseline_provenance": baseline_prov,
    }

    if comparison_rows:
        cmp_df = pd.DataFrame(comparison_rows)
        cmp_path = out_dir / "holdout_comparison.csv"
        cmp_df.to_csv(cmp_path, index=False)
        summary["outputs"]["holdout_comparison_csv"] = str(cmp_path)
        summary["n_holdout_comparisons"] = len(comparison_rows)

    summary["status_counts"] = (
        est_df["estimation_status"].value_counts().to_dict() if len(est_df) else {}
    )
    summary_path = out_dir / "run_summary.json"
    summary_path.write_text(
        json.dumps({k: v for k, v in summary.items() if not k.endswith("_rows")}, indent=2),
        encoding="utf-8",
    )
    summary["outputs"]["summary_json"] = str(summary_path)

    report_path = reports_dir / f"run_report_{stamp}.md"
    report_path.write_text(_render_report(summary, unsupported, techniques), encoding="utf-8")
    summary["outputs"]["report_md"] = str(report_path)

    (out_dir / "effective_run_config.yaml").write_text(
        yaml.safe_dump({k: v for k, v in cfg.items() if k != "paths_resolved"}, sort_keys=False),
        encoding="utf-8",
    )

    _emit(progress, "Run complete.")
    summary["package_root"] = str(PACKAGE_ROOT)
    summary["estimate_rows"] = estimate_rows
    return summary


def _lookup_validation(
    validation_df: pd.DataFrame,
    instrument: str,
    technique: str,
    note: str,
    dynamic: str,
) -> float | None:
    hits = validation_df[
        (validation_df["instrument"] == instrument)
        & (validation_df["technique"] == technique)
        & (validation_df["pitch_name_sounding"] == note)
        & (validation_df["dynamic"] == dynamic)
    ]
    if hits.empty:
        return None
    value = hits.iloc[0]["density_value"]
    return None if pd.isna(value) else float(value)


def _render_report(
    summary: dict[str, Any],
    unsupported: list[dict[str, Any]],
    techniques: list[str],
) -> str:
    lines = [
        f"# String technique density run ({summary['timestamp_utc']})",
        "",
        f"- Model version: `{summary.get('model_version')}`",
        f"- Baseline collections: `{summary.get('baseline_collection_ids')}`",
        f"- Pooling method: `{summary.get('pooling_method')}`",
        f"- Target metric: `{summary.get('target_metric_definition_id')}`",
        f"- Literature parameters active: **{summary.get('n_literature_parameters', 0)}**",
        f"- Estimate rows: **{summary.get('n_estimate_rows', 0)}**",
        "",
        "## Techniques",
        "",
    ]
    for tech in techniques:
        lines.append(f"- {TECHNIQUE_DISPLAY.get(tech, tech)} (`{tech}`)")
    if unsupported:
        lines.extend(["", "## Unsupported requested parameters", ""])
        for item in unsupported:
            lines.append(f"- `{item.get('parameter_name')}`: {item.get('reason')}")
    lines.extend(["", "## Outputs", ""])
    for key, value in (summary.get("outputs") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def lookup_single(
    instrument: str,
    technique: str,
    note: str,
    dynamic: str,
    run_config_path: Path | str | None = None,
    *,
    baseline_collection_ids: list[str] | None = None,
) -> dict[str, Any]:
    cfg = load_run_config(run_config_path)
    paths = cfg["paths_resolved"]
    lit = load_yaml(paths["literature_parameters"])
    parameters = lit.get("parameters") or []
    unsupported = lit.get("unsupported_requested_parameters") or []
    pooled_df, baseline_prov = build_baseline_table(
        cfg,
        baseline_collection_ids=baseline_collection_ids,
        run_config_path=run_config_path,
    )
    code = normalize_instrument(instrument)
    hit = lookup_pooled_density(pooled_df, instrument=code, note=note, dynamic=dynamic)
    prov = {**baseline_prov, **(hit or {})}
    ordinary = None if hit is None else hit.get("ordinary_density")
    result = estimate_cell(
        instrument=code,
        technique=technique,
        note=note,
        dynamic=dynamic,
        ordinary_density=ordinary,
        parameters=parameters,
        n_draws=int(cfg.get("n_draws", 5000)),
        random_seed=int(cfg.get("random_seed", 0)),
        metric=load_density_metric(paths["density_metric"]),
        unsupported_reasons=unsupported,
        baseline_provenance=prov,
    )
    payload = result.to_dict()
    run_resolved = resolve_run_collections(cfg)
    validation_ids = run_resolved["validation_collection_ids"]
    if validation_ids:
        validation_df = load_imported_or_ingest(validation_ids, run_config_path)
        measured = _lookup_validation(validation_df, code, technique, note, dynamic)
        payload.update(compare_to_holdout(result, measured))
        payload["holdout_available"] = measured is not None
    else:
        payload.update(compare_to_holdout(result, None))
        payload["holdout_available"] = False
    return payload
