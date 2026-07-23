"""Ordinary-bowing baseline build pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from string_technique_model.baseline.alignment import (
    DEFAULT_ALIGNMENT_KEY,
    attach_cell_ids,
    build_alignment_table,
    normalize_alignment_key,
    validate_pitch_transposition,
    write_alignment_report,
)
from string_technique_model.baseline.duplicates import (
    classify_repeat_observations,
    collapse_exact_import_duplicates,
)
from string_technique_model.baseline.eligibility import annotate_eligibility, normalize_value_status
from string_technique_model.baseline.manifest import (
    build_run_id,
    config_checksum,
    file_sha256,
    write_run_manifest,
)
from string_technique_model.baseline.outputs import write_baseline_outputs
from string_technique_model.baseline.pitch import ensure_sounding_midi
from string_technique_model.baseline.pooling import normalize_pooling_method, pool_cell
from string_technique_model.baseline.provenance import build_provenance_ledger
from string_technique_model.baseline.reliability import assign_reliability, completeness_score
from string_technique_model.collections.instruments_domain import ALLOWED_INSTRUMENTS
from string_technique_model.collections.metrics import MetricRegistry
from string_technique_model.collections.registry import CollectionRegistry
from string_technique_model.collections.service import load_imported_or_ingest
from string_technique_model.config import PACKAGE_ROOT, load_run_config, resolve_path

LOGGER = logging.getLogger(__name__)

SPECIAL_TECHNIQUES = frozenset(
    {"artificial_harmonic", "sul_ponticello", "sul_tasto", "con_sordino", "ponticello", "tastiera"}
)


@dataclass
class BaselineBuildResult:
    run_id: str
    baseline_long: pd.DataFrame
    excluded: pd.DataFrame
    alignment_table: pd.DataFrame
    provenance_ledger: pd.DataFrame
    manifest: dict[str, Any]
    output_files: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _baseline_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    run = cfg.get("run") or {}
    baseline = dict(run.get("baseline") or {})
    # Merge legacy pooling keys
    pooling = run.get("pooling") or {}
    if "pooling_method" not in baseline and pooling.get("method"):
        baseline["pooling_method"] = pooling["method"]
    if not baseline.get("collection_weights") and pooling.get("weights"):
        baseline["collection_weights"] = pooling["weights"]
    return baseline


def _resolve_collections(cfg: dict[str, Any], override: list[str] | None) -> list[str]:
    if override:
        return list(override)
    run = cfg.get("run") or {}
    ids = list(run.get("baseline_collection_ids") or [])
    if not ids:
        raise ValueError("No baseline collections selected. Pass --collections or set run.baseline_collection_ids.")
    return ids


def _filter_frame(
    frame: pd.DataFrame,
    *,
    instruments: list[str] | None,
    dynamics: list[str] | None,
    pitch_min: float | None,
    pitch_max: float | None,
) -> pd.DataFrame:
    out = frame
    if instruments:
        allowed = {str(i).lower() for i in instruments}
        out = out[out["instrument"].astype(str).str.lower().isin(allowed)]
    if dynamics:
        dyn = {str(d).lower() for d in dynamics}
        out = out[out["dynamic"].astype(str).str.lower().isin(dyn)]
    if pitch_min is not None and "pitch_midi_sounding" in out.columns:
        out = out[pd.to_numeric(out["pitch_midi_sounding"], errors="coerce") >= pitch_min]
    if pitch_max is not None and "pitch_midi_sounding" in out.columns:
        out = out[pd.to_numeric(out["pitch_midi_sounding"], errors="coerce") <= pitch_max]
    return out.copy()


def _source_checksums(collection_ids: list[str], registry: CollectionRegistry) -> dict[str, str]:
    out: dict[str, str] = {}
    for cid in collection_ids:
        entry = registry.get_entry(cid)
        for p in entry.get("data_paths") or []:
            path = resolve_path(p)
            if path.exists():
                try:
                    key = str(path.relative_to(PACKAGE_ROOT))
                except ValueError:
                    key = str(path)
                out[key] = file_sha256(path)
    return out


def _schema_versions(collection_ids: list[str], registry: CollectionRegistry) -> dict[str, str]:
    out: dict[str, str] = {}
    for cid in collection_ids:
        entry = registry.get_entry(cid)
        schema = entry.get("schema_mapping")
        if not schema:
            out[cid] = "unknown"
            continue
        path = resolve_path(schema)
        if path.exists():
            out[cid] = file_sha256(path)[:16]
        else:
            out[cid] = "missing"
    return out


def build_ordinary_baseline(
    run_config_path: Path | str | None = None,
    *,
    collection_ids: list[str] | None = None,
    metric_definition_id: str | None = None,
    pooling_method: str | None = None,
    instruments: list[str] | None = None,
    dynamics: list[str] | None = None,
    pitch_min: float | None = None,
    pitch_max: float | None = None,
    output_dir: Path | str | None = None,
    dry_run: bool = False,
    overwrite: bool = True,
    seed: int | None = None,
    strict: bool = False,
    write_wide: bool | None = None,
) -> BaselineBuildResult:
    cfg = load_run_config(run_config_path)
    run = cfg.get("run") or {}
    bcfg = _baseline_cfg(cfg)
    paths = cfg["paths_resolved"]

    selected = _resolve_collections(cfg, collection_ids)
    target_metric = metric_definition_id or str(run.get("target_metric_definition_id") or "ewsd_v1")
    method = normalize_pooling_method(
        pooling_method or str(bcfg.get("pooling_method") or "hierarchical_collection")
    )
    alignment_key = normalize_alignment_key(list(bcfg.get("alignment_key") or DEFAULT_ALIGNMENT_KEY))
    within_method = str(bcfg.get("within_collection_aggregation") or "no_aggregation")
    allow_missing_dynamic = bool(bcfg.get("allow_missing_dynamic", False))
    allow_interp = bool(bcfg.get("allow_interpolation", False))
    allow_extrap = bool(bcfg.get("allow_extrapolation", False))
    if allow_interp or allow_extrap:
        raise ValueError(
            "Interpolation/extrapolation are disabled in Phase 2. "
            "Set baseline.allow_interpolation/extrapolation to false."
        )

    accepted_compat = list(bcfg.get("accepted_metric_compatibility") or ["identical"])
    allow_conversion = bool(bcfg.get("allow_declared_metric_conversion", False))
    if bcfg.get("require_exact_metric_compatibility", True) and not allow_conversion:
        accepted_compat = ["identical"]

    allowed_value_statuses = list(bcfg.get("allowed_value_statuses") or ["measured"])
    user_weights = dict(bcfg.get("collection_weights") or {})

    selected_instruments = list(instruments or run.get("instruments") or sorted(ALLOWED_INSTRUMENTS))
    selected_dynamics = list(dynamics or run.get("dynamics") or [])
    rng_seed = seed if seed is not None else cfg.get("random_seed")

    out_dir = Path(output_dir or paths.get("baseline_dir") or (PACKAGE_ROOT / "outputs" / "baseline"))
    if out_dir.exists() and any(out_dir.iterdir()) and not overwrite and not dry_run:
        raise FileExistsError(f"Output directory exists and overwrite=False: {out_dir}")

    metric_registry = MetricRegistry.from_paths(paths["metric_definitions"], paths["metric_conversions"])
    registry = CollectionRegistry.from_yaml(paths.get("collections_registry"))

    raw = load_imported_or_ingest(selected, run_config_path)
    n_before = int(len(raw))
    raw = _filter_frame(
        raw,
        instruments=selected_instruments,
        dynamics=selected_dynamics or None,
        pitch_min=pitch_min,
        pitch_max=pitch_max,
    )

    # Ensure sounding MIDI is available for acoustic alignment (derive from name if needed).
    raw = ensure_sounding_midi(raw)

    warnings = validate_pitch_transposition(raw)

    eligible, excluded = annotate_eligibility(
        raw,
        target_metric_definition_id=target_metric,
        metric_registry=metric_registry,
        accepted_metric_compatibility=accepted_compat,
        allow_declared_metric_conversion=allow_conversion,
        allow_missing_dynamic=allow_missing_dynamic,
        allowed_value_statuses=allowed_value_statuses,
        apply_conversions=allow_conversion or ("identical" in accepted_compat),
    )

    # Always attach conversion provenance fields even for identical metrics
    if not eligible.empty and "original_density_value" not in eligible.columns:
        eligible = eligible.copy()
        eligible["original_density_value"] = eligible["density_value"]
        eligible["converted_density_value"] = eligible["density_value"]
        eligible["original_metric_definition_id"] = eligible["metric_definition_id"]
        eligible["target_metric_definition_id"] = target_metric
        eligible["conversion_id"] = None
        eligible["metric_conversion_applied"] = False

    eligible, dup_dropped = collapse_exact_import_duplicates(eligible)
    if not dup_dropped.empty:
        excluded = pd.concat([excluded, dup_dropped], ignore_index=True)

    eligible = attach_cell_ids(eligible, alignment_key=alignment_key)
    eligible = classify_repeat_observations(eligible, alignment_key)

    # Guard: no special techniques in eligible set
    if not eligible.empty and "technique" in eligible.columns:
        bad_tech = eligible[eligible["technique"].astype(str).str.lower().isin(SPECIAL_TECHNIQUES)]
        if not bad_tech.empty:
            raise RuntimeError("Special-technique rows leaked into ordinary baseline eligibility.")

    alignment_table = build_alignment_table(eligible, alignment_key=alignment_key)

    # Pool per analytical cell
    key_cols = [c for c in alignment_key if c in eligible.columns]
    baseline_rows: list[dict[str, Any]] = []
    created_at = datetime.now(timezone.utc).isoformat()

    source_checksums = _source_checksums(selected, registry)
    schema_versions = _schema_versions(selected, registry)
    conversion_version = file_sha256(Path(paths["metric_conversions"]))[:16]
    run_id = build_run_id(
        collection_ids=selected,
        source_checksums=source_checksums,
        schema_versions=schema_versions,
        metric_definition_id=target_metric,
        conversion_registry_version=conversion_version,
        alignment_key=alignment_key,
        pooling_method=method,
        pooling_parameters={
            "within_collection_aggregation": within_method,
            "collection_weights": user_weights,
            "accepted_metric_compatibility": accepted_compat,
            "allowed_value_statuses": allowed_value_statuses,
        },
        instruments=selected_instruments,
        dynamics=selected_dynamics,
        seed=int(rng_seed) if rng_seed is not None else None,
    )

    if eligible.empty:
        baseline_long = pd.DataFrame()
    else:
        for key_vals, group in eligible.groupby(key_cols, dropna=False, observed=True):
            if not isinstance(key_vals, tuple):
                key_vals = (key_vals,)
            key = {col: key_vals[i] for i, col in enumerate(key_cols)}
            cell_id = str(group["baseline_cell_id"].iloc[0])
            pooled = pool_cell(
                group,
                method=method,
                user_weights=user_weights or None,
                within_method=within_method,
            )
            status = str(pooled.get("status") or "pooled")
            if pooled.get("baseline_value") is None:
                baseline_status = "missing" if status in {"empty", "insufficient_variance_information"} else status
            else:
                baseline_status = "ok" if status in {"pooled", "single_collection", "pooled_equal_fallback", "no_pooling_first_collection"} else status

            statuses = sorted(
                {
                    normalize_value_status(v, collection_type=c)
                    for v, c in zip(group["measured_or_estimated"], group.get("collection_type", [None] * len(group)), strict=False)
                }
            )
            # Never relabel derived/pooled as measured
            if any(s in {"derived", "pooled_derived", "estimated"} for s in statuses):
                if "measured" in statuses and len(statuses) > 1:
                    mos = "mixed_derived"
                else:
                    mos = statuses[0] if len(statuses) == 1 else "pooled_derived"
            else:
                mos = "measured" if statuses == ["measured"] else (statuses[0] if statuses else "unknown")

            meta_score = float(
                np.mean(
                    [
                        completeness_score(
                            {str(k): v for k, v in row.to_dict().items()},
                            ["instrument", "technique", "pitch_midi_sounding", "dynamic", "metric_definition_id"],
                        )
                        for _, row in group.iterrows()
                    ]
                )
            )
            prov_score = float(
                np.mean(
                    [
                        completeness_score(
                            {str(k): v for k, v in row.to_dict().items()},
                            ["source_file", "source_row", "collection_id", "provenance", "record_id"],
                        )
                        for _, row in group.iterrows()
                    ]
                )
            )
            conversion_applied = bool(group.get("metric_conversion_applied", pd.Series([False])).astype(bool).any())
            conversion_ids = sorted(
                {str(x) for x in group.get("conversion_id", pd.Series(dtype=object)).dropna().unique()}
            )
            reliability = assign_reliability(
                number_of_collections=int(pooled.get("number_of_contributing_collections") or 0),
                number_of_observations=int(pooled.get("number_of_observations") or len(group)),
                measured_or_estimated=mos,
                metric_conversion_applied=conversion_applied,
                metadata_completeness=meta_score,
                provenance_completeness=prov_score,
                collection_heterogeneity=(
                    float(pooled["heterogeneity_statistic"])
                    if pooled.get("heterogeneity_statistic") is not None
                    else (
                        float(pooled["between_collection_variance"])
                        if pooled.get("between_collection_variance") is not None
                        else None
                    )
                ),
                pooling_status=baseline_status,
            )

            # Representative pitch names from first row
            first = group.iloc[0]
            coll_vals = pooled.get("collection_level_values") or {}
            coll_w = pooled.get("collection_weights") or {}
            baseline_rows.append(
                {
                    "baseline_cell_id": cell_id,
                    "target_metric_definition_id": target_metric,
                    "instrument": key.get("instrument", first.get("instrument")),
                    "technique": key.get("technique", first.get("technique")),
                    "pitch_name_sounding": first.get("pitch_name_sounding"),
                    "pitch_midi_sounding": key.get("pitch_midi_sounding", first.get("pitch_midi_sounding")),
                    "pitch_name_written": first.get("pitch_name_written"),
                    "pitch_midi_written": first.get("pitch_midi_written"),
                    "dynamic": key.get("dynamic", first.get("dynamic")),
                    "articulation": key.get("articulation", first.get("articulation")),
                    "string_name": key.get("string_name", first.get("string_name")),
                    "baseline_value": pooled.get("baseline_value"),
                    "baseline_mean": pooled.get("baseline_mean"),
                    "baseline_median": pooled.get("baseline_median"),
                    "baseline_sd": pooled.get("baseline_sd"),
                    "baseline_se": pooled.get("baseline_se"),
                    "baseline_q025": pooled.get("baseline_q025"),
                    "baseline_q500": pooled.get("baseline_q500"),
                    "baseline_q975": pooled.get("baseline_q975"),
                    "number_of_observations": int(pooled.get("number_of_observations") or len(group)),
                    "number_of_collections": int(pooled.get("number_of_contributing_collections") or 0),
                    "contributing_collection_ids": sorted(coll_vals.keys()),
                    "collection_values": coll_vals,
                    "collection_weights": coll_w,
                    "pooling_method": method,
                    "between_collection_variance": pooled.get("between_collection_variance"),
                    "heterogeneity_statistic": pooled.get("heterogeneity_statistic"),
                    "metric_conversion_applied": conversion_applied,
                    "conversion_ids": conversion_ids,
                    "baseline_reliability_grade": reliability["baseline_reliability_grade"],
                    "baseline_status": baseline_status if pooled.get("baseline_value") is not None else "missing",
                    "measured_or_estimated": mos,
                    "provenance": {
                        "run_id": run_id,
                        "contributing_record_ids": group["record_id"].astype(str).tolist()
                        if "record_id" in group.columns
                        else [],
                        "pooling_status": pooled.get("status"),
                        "uncertainty_status": pooled.get("uncertainty_status") or reliability.get("uncertainty_status"),
                    },
                    "run_id": run_id,
                    "created_at_utc": created_at,
                    **{f"align_{k}": v for k, v in key.items()},
                }
            )

        baseline_long = pd.DataFrame(baseline_rows)

    # Final scientific guards
    if not baseline_long.empty:
        instruments_present = set(baseline_long["instrument"].astype(str).str.lower().unique())
        if not instruments_present.issubset(ALLOWED_INSTRUMENTS):
            raise RuntimeError(f"Baseline contains unsupported instruments: {instruments_present - ALLOWED_INSTRUMENTS}")
        techniques_present = set(baseline_long["technique"].astype(str).str.lower().unique())
        if techniques_present - {"ordinary"}:
            raise RuntimeError(f"Baseline contains non-ordinary techniques: {techniques_present}")
        if (baseline_long["baseline_value"].fillna(0) == 0).any() and (
            baseline_long["baseline_value"].isna().any() is False
        ):
            # Zeros may be legitimate measured zeros; only warn if any missing filled — we never fill missing with 0.
            pass
        # Ensure unavailable uncertainty is null not 0-invented for non-probabilistic equal mean etc.
        if method in {"equal_collection_mean", "no_pooling", "robust_median"}:
            for col in ("baseline_se", "baseline_q025", "baseline_q975"):
                if col in baseline_long.columns:
                    # Leave values only if method produced them; equal_collection does not.
                    if method == "equal_collection_mean":
                        baseline_long[col] = np.nan

    if strict and not excluded.empty:
        LOGGER.warning("Strict mode: %s records excluded from baseline", len(excluded))

    report_path = Path(paths.get("reports_dir") or (PACKAGE_ROOT / "reports")) / "baseline_alignment_report.md"
    write_alignment_report(
        report_path,
        n_before=n_before,
        n_eligible=int(len(eligible)),
        n_excluded=int(len(excluded)),
        alignment_table=alignment_table,
        eligible=eligible,
        excluded=excluded,
        conflicting_metadata=warnings,
    )

    provenance_ledger = build_provenance_ledger(eligible, excluded, baseline_long)

    do_wide = bool(bcfg.get("write_wide_exports", True) if write_wide is None else write_wide)
    output_files: dict[str, str] = {}
    manifest: dict[str, Any] = {}
    if not dry_run:
        output_files = write_baseline_outputs(
            baseline_long,
            output_dir=out_dir,
            excluded=excluded,
            alignment_table=alignment_table,
            provenance_ledger=provenance_ledger,
            write_wide=do_wide,
        )
        output_files["baseline_alignment_report.md"] = str(report_path)
        manifest = write_run_manifest(
            out_dir / "run_manifest.json",
            run_id=run_id,
            collection_ids=selected,
            excluded_collections=[],
            metric_definition_id=target_metric,
            alignment_key=alignment_key,
            pooling_method=method,
            weights=user_weights,
            seed=int(rng_seed) if rng_seed is not None else None,
            source_checksums=source_checksums,
            configuration_checksums={
                "run": config_checksum({"run": run, "baseline": bcfg}),
                "metric_definitions": file_sha256(Path(paths["metric_definitions"]))[:32],
                "metric_conversions": conversion_version,
            },
            output_files=output_files,
            warnings=warnings,
        )
        output_files["run_manifest.json"] = str(out_dir / "run_manifest.json")
    else:
        manifest = {"run_id": run_id, "dry_run": True, "warnings": warnings}

    LOGGER.info(
        "Baseline build complete run_id=%s eligible=%s excluded=%s cells=%s method=%s",
        run_id,
        len(eligible),
        len(excluded),
        len(baseline_long),
        method,
    )
    return BaselineBuildResult(
        run_id=run_id,
        baseline_long=baseline_long,
        excluded=excluded,
        alignment_table=alignment_table,
        provenance_ledger=provenance_ledger,
        manifest=manifest,
        output_files=output_files,
        warnings=warnings,
    )


def inspect_baseline_config(run_config_path: Path | str | None = None) -> dict[str, Any]:
    cfg = load_run_config(run_config_path)
    run = cfg.get("run") or {}
    bcfg = _baseline_cfg(cfg)
    return {
        "baseline_collection_ids": list(run.get("baseline_collection_ids") or []),
        "target_metric_definition_id": run.get("target_metric_definition_id"),
        "instruments": run.get("instruments"),
        "allowed_techniques": run.get("allowed_techniques"),
        "dynamics": run.get("dynamics"),
        "baseline": bcfg,
    }


def validate_baseline_config(run_config_path: Path | str | None = None) -> dict[str, Any]:
    cfg = load_run_config(run_config_path)
    run = cfg.get("run") or {}
    bcfg = _baseline_cfg(cfg)
    errors: list[str] = []
    warnings: list[str] = []
    ids = list(run.get("baseline_collection_ids") or [])
    if not ids:
        errors.append("run.baseline_collection_ids is empty")
    method = normalize_pooling_method(str(bcfg.get("pooling_method") or ""))
    from string_technique_model.baseline.pooling import POOLING_METHODS

    if method not in POOLING_METHODS and method != "equal_collection_mean":
        errors.append(f"Unknown pooling_method: {method}")
    if bcfg.get("allow_interpolation"):
        errors.append("allow_interpolation must be false in Phase 2")
    if bcfg.get("allow_extrapolation"):
        errors.append("allow_extrapolation must be false in Phase 2")
    if method == "user_weighted_mean":
        weights = dict(bcfg.get("collection_weights") or {})
        try:
            from string_technique_model.baseline.weighted import validate_user_weights

            validate_user_weights(ids, weights)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    instruments = set(str(i).lower() for i in (run.get("instruments") or []))
    if instruments - ALLOWED_INSTRUMENTS:
        errors.append(f"Unsupported instruments in run config: {instruments - ALLOWED_INSTRUMENTS}")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "config": inspect_baseline_config(run_config_path)}


def compare_pooling_methods(
    collection_ids: list[str],
    methods: list[str],
    *,
    run_config_path: Path | str | None = None,
    metric_definition_id: str | None = None,
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for method in methods:
        result = build_ordinary_baseline(
            run_config_path,
            collection_ids=collection_ids,
            metric_definition_id=metric_definition_id,
            pooling_method=method,
            dry_run=True,
            overwrite=True,
        )
        frame = result.baseline_long
        summaries[method] = {
            "n_cells": int(len(frame)),
            "n_with_value": int(frame["baseline_value"].notna().sum()) if not frame.empty else 0,
            "mean_baseline_value": float(frame["baseline_value"].mean()) if not frame.empty else None,
            "run_id": result.run_id,
        }
    return {"collections": collection_ids, "methods": summaries}
