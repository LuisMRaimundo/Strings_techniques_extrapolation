"""Declarative YAML → canonical mapping (no silent invention of metadata)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from string_technique_model.collections.canonical import CANONICAL_COLUMNS
from string_technique_model.collections.instruments_domain import apply_instrument_domain
from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.stable_seed import stable_record_id


def relativize_source_path(path: str | Path, root: Path | None = None) -> str:
    root = root or PACKAGE_ROOT
    path = Path(path)
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_missing_marker(value: Any, markers: list[str]) -> bool:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return True
    if pd.isna(value):
        return True
    text = str(value).strip()
    return text in markers


def map_raw_to_canonical(
    raw: pd.DataFrame,
    *,
    schema: dict[str, Any],
    collection_meta: dict[str, Any],
    source_file: str,
    source_sheet: str | None = None,
    source_table: str | None = None,
    import_timestamp_utc: str | None = None,
) -> pd.DataFrame:
    columns_map: dict[str, str] = dict(schema.get("columns") or {})
    constants: dict[str, Any] = dict(schema.get("constants") or {})
    value_maps: dict[str, dict[str, Any]] = dict(schema.get("value_maps") or {})
    markers = [str(m) for m in (schema.get("missing_value_markers") or ["", "NA", "NaN", "null"])]
    mapping_version = str(schema.get("schema_mapping_version") or "1.0")
    missing_by_design_cols = set(schema.get("missing_by_design_fields") or [])

    source_file_rel = relativize_source_path(source_file)
    work = raw.copy()

    # Decimal separator / type coercion helpers (declarative)
    for col, rule in (schema.get("type_coercion") or {}).items():
        if col not in work.columns:
            continue
        if rule.get("decimal_comma"):
            work[col] = work[col].astype(str).str.replace(",", ".", regex=False)

    out = pd.DataFrame(index=work.index.copy())
    out["source_row"] = np.arange(len(work), dtype=int)
    out["source_file"] = source_file_rel
    out["source_sheet"] = source_sheet
    out["source_table"] = source_table or collection_meta.get("table_name")
    out["collection_id"] = collection_meta["collection_id"]
    out["collection_display_name"] = collection_meta.get("display_name")
    out["collection_type"] = collection_meta.get("collection_type")
    out["import_timestamp_utc"] = import_timestamp_utc
    out["schema_mapping_version"] = mapping_version
    out["transformations_applied"] = "yaml_column_map;value_maps;constants"
    out["conversions_applied"] = ""  # filled only when an explicit conversion is applied later

    mapped_fields: list[str] = []
    for canonical, source_col in columns_map.items():
        if source_col in work.columns:
            series = work[source_col]
            series = series.map(lambda v: pd.NA if _is_missing_marker(v, markers) else v)
            out[canonical] = series
            mapped_fields.append(canonical)
        else:
            out[canonical] = pd.NA

    for key, value in constants.items():
        if key not in out.columns or out[key].isna().all():
            out[key] = value

    technique_map_status = []
    for field, mapping in value_maps.items():
        if field not in out.columns:
            continue
        # Instrument aliases are applied by the strict domain module (exact match only).
        if field == "instrument":
            continue
        mapped_vals = []
        statuses = []
        for v in out[field]:
            if pd.isna(v):
                mapped_vals.append(pd.NA)
                statuses.append("missing")
                continue
            key = v if v in mapping else str(v)
            if key in mapping:
                mapped_vals.append(mapping[key])
                statuses.append("mapped")
            else:
                # Keep original; do not invent a canonical code.
                mapped_vals.append(v)
                statuses.append("unmapped")
        out[field] = mapped_vals
        if field == "technique":
            technique_map_status = statuses

    out = apply_instrument_domain(out)
    if technique_map_status:
        out["technique_mapping_status"] = technique_map_status
    elif "technique_mapping_status" not in out.columns:
        out["technique_mapping_status"] = ["n/a"] * len(out)

    # Deterministic record_id if absent
    if "record_id" not in out.columns or out["record_id"].isna().all():
        out["record_id"] = [
            stable_record_id(
                collection_meta["collection_id"],
                source_file_rel,
                cast(int, int(cast(Any, row))),
                out.at[idx, "instrument"] if "instrument" in out.columns else "",
                out.at[idx, "technique"] if "technique" in out.columns else "",
                out.at[idx, "pitch_name_sounding"] if "pitch_name_sounding" in out.columns else "",
                out.at[idx, "dynamic"] if "dynamic" in out.columns else "",
            )
            for idx, row in zip(out.index, out["source_row"], strict=True)
        ]
    else:
        # Fill only missing ids deterministically
        for idx in out.index[out["record_id"].isna()]:
            out.at[idx, "record_id"] = stable_record_id(
                collection_meta["collection_id"],
                source_file_rel,
                cast(int, int(cast(Any, out.at[idx, "source_row"]))),
            )

    # Missingness status per row for density
    statuses = []
    for idx in out.index:
        dens = out.at[idx, "density_value"] if "density_value" in out.columns else pd.NA
        if pd.notna(dens):
            statuses.append("observed")
        elif "density_value" in missing_by_design_cols:
            statuses.append("missing_by_design")
        elif "density_value" in mapped_fields:
            statuses.append("missing_in_source")
        else:
            statuses.append("missing_by_design")
    if "missingness_status" not in out.columns or out["missingness_status"].isna().all():
        out["missingness_status"] = statuses

    for col in CANONICAL_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    missing_fields = [col for col in CANONICAL_COLUMNS if out[col].isna().all()]
    out["missing_by_design_fields"] = ";".join(missing_fields)

    # Provenance: never replace with generic "pooled"
    base_prov = constants.get("provenance")
    if base_prov:
        out["provenance"] = (
            f"{base_prov} | collection={collection_meta['collection_id']}; "
            f"schema_mapping={collection_meta.get('schema_mapping')}; "
            f"schema_mapping_version={mapping_version}; source_file={source_file_rel}"
        )
    else:
        out["provenance"] = (
            f"collection={collection_meta['collection_id']}; "
            f"schema_mapping={collection_meta.get('schema_mapping')}; "
            f"schema_mapping_version={mapping_version}; source_file={source_file_rel}"
        )

    # Never coerce missing density to zero
    if "density_value" in out.columns:
        # empty strings already NA; ensure no accidental fillna(0)
        pass

    return out[CANONICAL_COLUMNS].copy()
