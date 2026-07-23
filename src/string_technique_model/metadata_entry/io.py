"""Import/export for metadata collections (CSV / JSON / Parquet / canonical)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from string_technique_model.metadata_entry.models import SCHEMA_VERSION, MetadataEntryRecord


def _rows_to_dicts(rows: list[MetadataEntryRecord]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        d = r.model_dump()
        # Preserve nulls; stringify lists for CSV friendliness at export time
        out.append(d)
    return out


def export_json(rows: list[MetadataEntryRecord], path: Path | str, *, full_schema: bool = True) -> Path:
    path = Path(path)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "n_records": len(rows),
        "records": _rows_to_dicts(rows),
        "full_schema": full_schema,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def export_csv(
    rows: list[MetadataEntryRecord],
    path: Path | str,
    *,
    columns: list[str] | None = None,
) -> Path:
    path = Path(path)
    dicts = _rows_to_dicts(rows)
    if not dicts:
        path.write_text("", encoding="utf-8")
        return path
    if columns is None:
        # Union of keys, stable-ish order
        keys: list[str] = []
        seen: set[str] = set()
        for d in dicts:
            for k in d:
                if k not in seen:
                    seen.add(k)
                    keys.append(k)
        columns = keys
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for d in dicts:
            row = {}
            for k in columns:
                v = d.get(k)
                if v is None:
                    row[k] = ""
                elif isinstance(v, (list, dict)):
                    row[k] = json.dumps(v, ensure_ascii=False)
                else:
                    row[k] = v
            writer.writerow(row)
    return path


def export_parquet(rows: list[MetadataEntryRecord], path: Path | str) -> Path:
    path = Path(path)
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Parquet export requires pandas") from exc
    dicts = _rows_to_dicts(rows)
    # Normalize list columns to JSON strings for parquet stability
    for d in dicts:
        for k, v in list(d.items()):
            if isinstance(v, (list, dict)):
                d[k] = json.dumps(v, ensure_ascii=False)
    frame = pd.DataFrame(dicts)
    try:
        frame.to_parquet(path, index=False)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Parquet engine unavailable: {exc}") from exc
    # Sidecar schema version
    path.with_suffix(path.suffix + ".meta.json").write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "n_records": len(rows)}, indent=2),
        encoding="utf-8",
    )
    return path


def import_json(path: Path | str) -> tuple[list[MetadataEntryRecord], list[str]]:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    records_raw = data.get("records") if isinstance(data, dict) else data
    if not isinstance(records_raw, list):
        raise ValueError("JSON must contain a list of records or {records: [...]}")
    return _parse_records(records_raw)


def import_csv(path: Path | str, *, column_map: dict[str, str] | None = None) -> tuple[list[MetadataEntryRecord], list[str]]:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        raw_rows = list(reader)
    mapped: list[dict[str, Any]] = []
    for row in raw_rows:
        item: dict[str, Any] = {}
        for k, v in row.items():
            key = (column_map or {}).get(k, k)
            if v == "":
                item[key] = None
            else:
                item[key] = v
        # Preserve unknown columns
        mapped.append(item)
    return _parse_records(mapped)


def import_parquet(path: Path | str) -> tuple[list[MetadataEntryRecord], list[str]]:
    path = Path(path)
    import pandas as pd

    frame = pd.read_parquet(path)
    records: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        item: dict[str, Any] = {}
        for k, v in raw.items():
            try:
                item[str(k)] = None if v is None or pd.isna(v) else v
            except (TypeError, ValueError):
                item[str(k)] = v
        records.append(item)
    return _parse_records(records)


def _parse_records(raw_rows: list[dict[str, Any]]) -> tuple[list[MetadataEntryRecord], list[str]]:
    records: list[MetadataEntryRecord] = []
    problems: list[str] = []
    for i, row in enumerate(raw_rows):
        try:
            # Keep unknown columns via extra=allow
            cleaned = {k: (None if v == "" else v) for k, v in row.items()}
            records.append(MetadataEntryRecord.from_mapping(cleaned))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"row {i}: {exc}")
            # Do not discard silently — keep a stub with notes
            stub = MetadataEntryRecord.new_empty()
            stub.notes = f"IMPORT_INVALID: {exc}"
            stub.validation_status = "error"
            for k, v in row.items():
                if k not in stub.model_fields:
                    setattr(stub, k, v)
            records.append(stub)
    return records, problems
