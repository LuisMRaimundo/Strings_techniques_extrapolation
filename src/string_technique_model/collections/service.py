from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from string_technique_model.collections.canonical import PHASE1_REQUIRED_COLUMNS
from string_technique_model.collections.instruments_domain import (
    rejected_records_table,
    split_supported_instruments,
)
from string_technique_model.collections.metrics import MetricRegistry
from string_technique_model.collections.registry import CollectionRegistry
from string_technique_model.config import PACKAGE_ROOT, load_run_config, resolve_path
from string_technique_model.stable_seed import stable_hex

LOGGER = logging.getLogger("string_technique_model.collections")


class CollectionServiceError(RuntimeError):
    """Raised for recoverable collection CLI/service failures."""


def _metric_registry_from_run(cfg: dict[str, Any]) -> MetricRegistry:
    paths = cfg["paths_resolved"]
    return MetricRegistry.from_paths(
        paths.get("metric_definitions") or (PACKAGE_ROOT / "configs" / "metric_definitions.yaml"),
        paths.get("metric_conversions") or (PACKAGE_ROOT / "configs" / "metric_conversions.yaml"),
    )


def _target_metric(cfg: dict[str, Any]) -> str:
    run = cfg.get("run") or {}
    return str(run.get("target_metric_definition_id") or "ewsd_v1")


def list_collections(run_config_path: Path | str | None = None) -> list[dict[str, Any]]:
    cfg = load_run_config(run_config_path)
    reg_path = cfg["paths_resolved"].get("collections_registry")
    registry = CollectionRegistry.from_yaml(reg_path)
    return registry.list()


def inspect_collection(
    collection_id: str,
    run_config_path: Path | str | None = None,
) -> dict[str, Any]:
    cfg = load_run_config(run_config_path)
    registry = CollectionRegistry.from_yaml(cfg["paths_resolved"].get("collections_registry"))
    adapter = registry.get_adapter(collection_id)
    return adapter.inspect().to_dict()


def validate_collection(
    collection_id: str,
    run_config_path: Path | str | None = None,
) -> dict[str, Any]:
    cfg = load_run_config(run_config_path)
    registry = CollectionRegistry.from_yaml(cfg["paths_resolved"].get("collections_registry"))
    metrics = _metric_registry_from_run(cfg)
    target = _target_metric(cfg)
    adapter = registry.get_adapter(collection_id)
    raw = adapter.load_raw()
    canonical = adapter.map_to_canonical_schema(raw)
    schema_report = adapter.validate_schema(canonical)
    compat = adapter.validate_metric_compatibility(canonical, metrics, target)
    enriched = adapter.enrich(canonical, metrics, target)
    return {
        "schema": schema_report.to_dict(),
        "compatibility": compat.to_dict(),
        "quality": adapter.quality_summary(enriched),
        "inventory_summary": _inventory_stats(enriched),
    }


def import_collection(
    collection_id: str,
    run_config_path: Path | str | None = None,
    *,
    dry_run: bool = False,
    overwrite: bool = True,
    include_invalid_records: bool = False,
) -> dict[str, Any]:
    from string_technique_model.io import require_parquet_engine

    # Fail once and early: Parquet is mandatory for collection import outputs.
    require_parquet_engine()
    cfg = load_run_config(run_config_path)
    paths = cfg["paths_resolved"]
    registry = CollectionRegistry.from_yaml(paths.get("collections_registry"))
    metrics = _metric_registry_from_run(cfg)
    target = _target_metric(cfg)
    adapter = registry.get_adapter(collection_id)
    entry = registry.get_entry(collection_id)
    if not entry.get("enabled", True):
        raise CollectionServiceError(f"Collection {collection_id!r} is disabled in the registry")

    LOGGER.info(
        "Importing collection_id=%s dry_run=%s include_invalid_records=%s",
        collection_id,
        dry_run,
        include_invalid_records,
    )
    raw = adapter.load_raw()
    source_paths = [resolve_path(p) for p in entry.get("data_paths") or []]
    source_mtimes = {str(p): p.stat().st_mtime_ns for p in source_paths if p.exists()}

    canonical = adapter.map_to_canonical_schema(raw)
    schema_report = adapter.validate_schema(canonical)
    if not schema_report.ok:
        raise CollectionServiceError(
            f"Schema validation failed for {collection_id}: {schema_report.errors}"
        )
    compat = adapter.validate_metric_compatibility(canonical, metrics, target)
    enriched = adapter.enrich(canonical, metrics, target)
    accepted, rejected = split_supported_instruments(enriched)
    scientific = enriched if include_invalid_records else accepted
    adapter.assert_sources_unchanged()

    for path_str, mtime in source_mtimes.items():
        if Path(path_str).stat().st_mtime_ns != mtime:
            raise CollectionServiceError(f"Source file was modified during import: {path_str}")

    imported_dir = Path(paths.get("imported_dir") or (PACKAGE_ROOT / "outputs" / "imported"))
    rejected_dir = Path(paths.get("rejected_dir") or (PACKAGE_ROOT / "outputs" / "rejected"))
    parquet_path = imported_dir / f"{collection_id}.parquet"
    if parquet_path.exists() and not overwrite and not dry_run:
        raise CollectionServiceError(
            f"Output exists and --overwrite is false: {parquet_path}"
        )

    import_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content_fp = _canonical_content_fingerprint(scientific)
    result = {
        "collection_id": collection_id,
        "n_records": int(len(scientific)),
        "n_records_accepted": int(len(accepted)),
        "n_records_rejected": int(len(rejected)),
        "content_fingerprint": content_fp,
        "schema_ok": schema_report.ok,
        "metric_compatibility_status": compat.status,
        "collection_ids_present": sorted(set(scientific["collection_id"].astype(str)))
        if len(scientific)
        else [],
        "pooling_performed": False,
        "modelling_performed": False,
        "dry_run": dry_run,
        "include_invalid_records": include_invalid_records,
        "validation_warnings": schema_report.warnings,
        "inventory_summary": _inventory_stats(scientific),
    }

    if dry_run:
        LOGGER.info(
            "Dry-run complete for %s (accepted=%s rejected=%s)",
            collection_id,
            len(accepted),
            len(rejected),
        )
        return result

    parquet_path = adapter.export_canonical(scientific, imported_dir)
    rejected_dir.mkdir(parents=True, exist_ok=True)
    rejected_path = rejected_dir / f"{collection_id}_rejected_records.csv"
    rejected_records_table(rejected, import_timestamp_utc=import_ts).to_csv(
        rejected_path, index=False
    )

    meta_path = imported_dir / f"{collection_id}.meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "collection_id": collection_id,
                "imported_at_utc": import_ts,
                "n_records": int(len(scientific)),
                "n_records_accepted": int(len(accepted)),
                "n_records_rejected": int(len(rejected)),
                "content_fingerprint": content_fp,
                "metric_compatibility_status": compat.status,
                "phase": "phase1_collection_ingestion",
                "pooling_performed": False,
                "modelling_performed": False,
                "include_invalid_records": include_invalid_records,
                "collection_type": entry.get("collection_type"),
                "measured_or_estimated": entry.get("measured_or_estimated"),
                "rejected_records_csv": str(rejected_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    reports_dir = Path(paths["reports_dir"]) / "collections"
    reports_dir.mkdir(parents=True, exist_ok=True)
    inventory = adapter.inspect()
    inventory_path = reports_dir / f"{collection_id}_inventory.md"
    quality_path = reports_dir / f"{collection_id}_quality_report.md"
    compat_path = reports_dir / f"{collection_id}_compatibility_report.md"

    inventory_path.write_text(
        _render_inventory(inventory.to_dict(), scientific, schema_report.to_dict()),
        encoding="utf-8",
    )
    quality_path.write_text(
        _render_quality(
            collection_id,
            adapter.quality_summary(enriched),
            schema_report.to_dict(),
        ),
        encoding="utf-8",
    )
    compat_path.write_text(_render_compatibility(compat.to_dict()), encoding="utf-8")

    missing_phase1 = [c for c in PHASE1_REQUIRED_COLUMNS if c not in scientific.columns]
    if missing_phase1 and len(scientific):
        raise CollectionServiceError(f"Canonical export missing Phase-1 columns: {missing_phase1}")

    result.update(
        {
            "parquet": str(parquet_path),
            "meta": str(meta_path),
            "rejected_records_csv": str(rejected_path),
            "reports": {
                "inventory": str(inventory_path),
                "quality": str(quality_path),
                "compatibility": str(compat_path),
            },
        }
    )
    LOGGER.info(
        "Imported %s -> %s (accepted=%s rejected=%s)",
        collection_id,
        parquet_path,
        len(accepted),
        len(rejected),
    )
    return result


def compare_collections(
    collection_ids: list[str],
    run_config_path: Path | str | None = None,
) -> dict[str, Any]:
    cfg = load_run_config(run_config_path)
    paths = cfg["paths_resolved"]
    registry = CollectionRegistry.from_yaml(paths.get("collections_registry"))
    metrics = _metric_registry_from_run(cfg)
    target = _target_metric(cfg)

    summaries = []
    frames = []
    for cid in collection_ids:
        adapter = registry.get_adapter(cid)
        raw = adapter.load_raw()
        canonical = adapter.map_to_canonical_schema(raw)
        enriched = adapter.enrich(canonical, metrics, target)
        frames.append(enriched)
        compat = adapter.validate_metric_compatibility(canonical, metrics, target)
        summaries.append(
            {
                "collection_id": cid,
                "n_records": int(len(enriched)),
                "instruments": sorted(enriched["instrument"].dropna().astype(str).unique()),
                "techniques": sorted(enriched["technique"].dropna().astype(str).unique()),
                "metric_definition_ids": sorted(
                    enriched["metric_definition_id"].dropna().astype(str).unique()
                ),
                "metric_compatibility_status": compat.status,
                "compatibility_reason": compat.reason,
                "collection_type": registry.get_entry(cid).get("collection_type"),
            }
        )

    pairwise = []
    for i, a in enumerate(collection_ids):
        for b in collection_ids[i + 1 :]:
            entry_a = registry.get_entry(a)
            entry_b = registry.get_entry(b)
            result = metrics.compare(
                str(entry_a.get("metric_definition_id")),
                str(entry_b.get("metric_definition_id")),
            )
            to_target_a = metrics.compare(str(entry_a.get("metric_definition_id")), target)
            to_target_b = metrics.compare(str(entry_b.get("metric_definition_id")), target)
            can_combine = to_target_a.status in {
                "identical",
                "compatible_after_unit_conversion",
                "compatible_after_declared_transformation",
            } and to_target_b.status in {
                "identical",
                "compatible_after_unit_conversion",
                "compatible_after_declared_transformation",
            }
            pairwise.append(
                {
                    "collection_a": a,
                    "collection_b": b,
                    "direct_status": result.status,
                    "direct_reason": result.reason,
                    "can_combine_against_target": can_combine,
                    "a_vs_target": to_target_a.status,
                    "b_vs_target": to_target_b.status,
                }
            )

    report = {
        "target_metric_definition_id": target,
        "collections": summaries,
        "pairwise": pairwise,
        "pooling_performed": False,
        "modelling_performed": False,
    }
    out = Path(paths["reports_dir"]) / "collections" / "comparison_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(out)
    report["n_collections"] = len(collection_ids)
    report["total_records"] = int(sum(len(f) for f in frames))
    return report


def register_collection(
    collection_id: str,
    *,
    config_path: Path | str,
    display_name: str | None = None,
    data_paths: list[str] | None = None,
    fmt: str = "csv",
    schema_mapping: str | None = None,
    metric_definition_id: str = "ewsd_v1",
    collection_type: str = "measured",
    default_roles: list[str] | None = None,
    measured_or_estimated: str = "measured",
    notes: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    entry = {
        "collection_id": collection_id,
        "display_name": display_name or collection_id,
        "enabled": True,
        "collection_type": collection_type,
        "data_paths": data_paths or [],
        "format": fmt,
        "schema_mapping": schema_mapping or f"configs/schemas/{collection_id}.yaml",
        "metric_definition_id": metric_definition_id,
        "default_roles": default_roles or ["baseline"],
        "citation_id": collection_id.upper(),
        "licence": None,
        "measured_or_estimated": measured_or_estimated,
        "notes": notes,
    }
    if dry_run:
        return {"dry_run": True, "entry": entry}
    registry = CollectionRegistry.from_yaml(config_path)
    registry.register_entry(entry, config_path)
    return entry


def load_imported_or_ingest(
    collection_ids: list[str],
    run_config_path: Path | str | None = None,
    *,
    force_reimport: bool = False,
) -> pd.DataFrame:
    cfg = load_run_config(run_config_path)
    paths = cfg["paths_resolved"]
    imported_dir = Path(paths.get("imported_dir") or (PACKAGE_ROOT / "outputs" / "imported"))
    frames = []
    for cid in collection_ids:
        parquet = imported_dir / f"{cid}.parquet"
        if force_reimport or not parquet.exists():
            import_collection(cid, run_config_path)
        frames.append(pd.read_parquet(imported_dir / f"{cid}.parquet"))
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    if out["collection_id"].isna().any():
        raise CollectionServiceError("Imported records missing collection_id")
    return out


def _canonical_content_fingerprint(frame: pd.DataFrame) -> str:
    cols = [c for c in PHASE1_REQUIRED_COLUMNS if c in frame.columns]
    work = frame[cols].copy()
    sort_cols = [c for c in ("collection_id", "record_id", "source_row") if c in work.columns]
    if sort_cols:
        work = work.sort_values(sort_cols, kind="mergesort")
    payload = work.to_csv(index=False)
    return stable_hex(payload, n_chars=32)


def _inventory_stats(frame: pd.DataFrame) -> dict[str, Any]:
    def _uniq(col: str) -> list[str]:
        if col not in frame.columns:
            return []
        return sorted(frame[col].dropna().astype(str).unique().tolist())

    pitches = _uniq("pitch_name_sounding")
    return {
        "instruments": _uniq("instrument"),
        "techniques": _uniq("technique"),
        "dynamics": _uniq("dynamic"),
        "metric_definitions": _uniq("metric_definition_id"),
        "pitch_range": [pitches[0], pitches[-1]] if pitches else [],
        "n_missing_density": int(frame["density_value"].isna().sum())
        if "density_value" in frame.columns
        else None,
        "n_duplicates": int(frame.duplicated(subset=["record_id"]).sum())
        if "record_id" in frame.columns
        else None,
    }


def _render_inventory(
    inventory: dict[str, Any],
    frame: pd.DataFrame,
    schema: dict[str, Any] | None = None,
) -> str:
    stats = _inventory_stats(frame)
    schema = schema or {}
    lines = [
        f"# Collection inventory: {inventory['collection_id']}",
        "",
        f"- Display name: {inventory.get('display_name')}",
        f"- Collection type: `{inventory.get('collection_type')}`",
        f"- Measured or estimated: `{inventory.get('measured_or_estimated')}`",
        f"- Format: `{inventory.get('format')}`",
        f"- Enabled: {inventory.get('enabled')}",
        f"- Default roles: {inventory.get('default_roles') or inventory.get('default_role')}",
        f"- Metric definition: `{inventory.get('metric_definition_id')}`",
        f"- Files found: {inventory.get('n_files_found')}",
        f"- Raw rows: {inventory.get('n_raw_rows')}",
        f"- Canonical rows: {len(frame)}",
        "",
        "## Source paths",
        "",
    ]
    for p in inventory.get("data_paths") or []:
        lines.append(f"- `{p}`")
    lines.extend(["", "## Source columns", ""])
    for c in inventory.get("columns") or []:
        lines.append(f"- `{c}`")
    lines.extend(["", "## Canonical columns", ""])
    for c in frame.columns:
        lines.append(f"- `{c}`")
    lines.extend(
        [
            "",
            "## Content summary",
            "",
            f"- Instruments: {stats['instruments']}",
            f"- Techniques: {stats['techniques']}",
            f"- Dynamics: {stats['dynamics']}",
            f"- Pitch range: {stats['pitch_range']}",
            f"- Metric definitions: {stats['metric_definitions']}",
            f"- Missing density values: {stats['n_missing_density']}",
            f"- Duplicate record_ids: {stats['n_duplicates']}",
            "",
            "## Validation",
            "",
            f"- Schema OK: {schema.get('ok')}",
            f"- Errors: {schema.get('errors')}",
            f"- Warnings: {schema.get('warnings')}",
            f"- Details: `{json.dumps(schema.get('details') or {}, ensure_ascii=True)}`",
            "",
            "## Identity",
            "",
            f"- Distinct collection_id values: {sorted(set(frame['collection_id'].astype(str)))}",
            "",
        ]
    )
    if inventory.get("notes"):
        lines.extend(["## Notes", "", str(inventory["notes"]), ""])
    return "\n".join(lines)


def _render_quality(collection_id: str, quality: dict[str, Any], schema: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Quality report: {collection_id}",
            "",
            f"- Schema OK: {schema.get('ok')}",
            f"- Errors: {schema.get('errors')}",
            f"- Warnings: {schema.get('warnings')}",
            "",
            "## Summary",
            "",
            "```json",
            json.dumps(quality, indent=2),
            "```",
            "",
            "## Details",
            "",
            "```json",
            json.dumps(schema.get("details") or {}, indent=2),
            "```",
            "",
        ]
    )


def _render_compatibility(compat: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Compatibility report: {compat.get('collection_id')}",
            "",
            f"- Target / comparison metric: `{compat.get('target_metric_definition_id')}`",
            f"- Status: `{compat.get('status')}`",
            f"- Reason: {compat.get('reason')}",
            f"- Records: {compat.get('n_records')}",
            f"- Required conversion: {compat.get('required_conversion')}",
            f"- Uncertainty introduced: {compat.get('uncertainty_introduced')}",
            f"- Allowed operations: {compat.get('allowed_operations')}",
            f"- Prohibited operations: {compat.get('prohibited_operations')}",
            "",
            "## Per-metric status",
            "",
            "```json",
            json.dumps(compat.get("per_metric_status") or {}, indent=2),
            "```",
            "",
            "## Notes",
            "",
            "Equal metric *names* do not imply compatible metrics. Compatibility is",
            "determined only by `metric_definition_id` entries in",
            "`configs/metric_definitions.yaml` and explicit conversions in",
            "`configs/metric_conversions.yaml`.",
            "",
        ]
    )
