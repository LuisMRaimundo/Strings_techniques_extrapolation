"""Format loaders via a registry/factory (no collection-name conditionals)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd


class LoaderError(ValueError):
    """Raised when a source file cannot be loaded as a metric table."""


LoaderFn = Callable[..., pd.DataFrame]

_LOADERS: dict[str, LoaderFn] = {}


def register_loader(*names: str) -> Callable[[LoaderFn], LoaderFn]:
    def deco(fn: LoaderFn) -> LoaderFn:
        for name in names:
            _LOADERS[name.lower()] = fn
        return fn

    return deco


@register_loader("csv")
def _load_csv(path: Path, **_: Any) -> pd.DataFrame:
    return pd.read_csv(path)


@register_loader("tsv")
def _load_tsv(path: Path, **_: Any) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t")


@register_loader("xlsx")
def _load_xlsx(path: Path, sheet_name: str | None = None, **_: Any) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name or 0)


@register_loader("parquet")
def _load_parquet(path: Path, **_: Any) -> pd.DataFrame:
    return pd.read_parquet(path)


@register_loader("json")
def _load_json(path: Path, **_: Any) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict):
        if "records" in payload and isinstance(payload["records"], list):
            return pd.DataFrame(payload["records"])
        if "spectral_data" in payload:
            return _nested_dict_to_frame(payload, {})
        if all(isinstance(v, dict) for v in payload.values()):
            return pd.DataFrame(payload).T.reset_index(names="record_id_from_key")
    raise LoaderError(f"JSON root must be a list of records or a recognized object: {path}")


@register_loader("jsonl", "json_lines")
def _load_jsonl(path: Path, **_: Any) -> pd.DataFrame:
    return pd.read_json(path, lines=True)


@register_loader("sqlite")
def _load_sqlite(path: Path, sqlite_table: str | None = None, sheet_name: str | None = None, **_: Any) -> pd.DataFrame:
    table = sqlite_table or sheet_name
    if not table:
        raise LoaderError("sqlite format requires table_name/sqlite_table/sheet_name")
    with sqlite3.connect(path) as conn:
        return pd.read_sql_query(f'SELECT * FROM "{table}"', conn)


@register_loader("nested_spectral_json")
def _load_nested(path: Path, nested_spectral_options: dict[str, Any] | None = None, **_: Any) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LoaderError("nested_spectral_json expects a JSON object")
    return _nested_dict_to_frame(payload, nested_spectral_options or {})


OPTIONAL_UNSUPPORTED_FORMATS = {
    "wav",
    "aiff",
    "numpy",
    "hdf5",
    "zarr",
    "fft",
    "psd",
    "stft",
}


def supported_formats() -> list[str]:
    return sorted(_LOADERS)


def load_table(
    path: Path | str,
    fmt: str,
    *,
    sheet_name: str | None = None,
    sqlite_table: str | None = None,
    nested_spectral_options: dict[str, Any] | None = None,
) -> pd.DataFrame:
    path = Path(path)
    fmt = fmt.lower().strip()
    if not path.exists():
        raise FileNotFoundError(f"Collection data file not found: {path}")
    if fmt in OPTIONAL_UNSUPPORTED_FORMATS:
        raise LoaderError(
            f"Format {fmt!r} is recognized but not implemented as a table loader yet. "
            "Provide a precomputed metric table (csv/tsv/xlsx/parquet/json/jsonl)."
        )
    try:
        loader = _LOADERS[fmt]
    except KeyError as exc:
        raise LoaderError(f"Unsupported format: {fmt!r}. Supported: {supported_formats()}") from exc
    return loader(
        path,
        sheet_name=sheet_name,
        sqlite_table=sqlite_table,
        nested_spectral_options=nested_spectral_options,
    )


def _nested_dict_to_frame(payload: dict[str, Any], options: dict[str, Any]) -> pd.DataFrame:
    spectral_key = options.get("spectral_key", "spectral_data")
    instrument = payload.get(options.get("instrument_field", "instrument"))
    technique = payload.get(
        options.get("technique_field", "technique"),
        payload.get("source_technique", "ordinary"),
    )
    spectral = payload.get(spectral_key) or {}
    rows: list[dict[str, Any]] = []
    for note, dyn_map in spectral.items():
        if not isinstance(dyn_map, dict):
            continue
        for dynamic, value in dyn_map.items():
            rows.append(
                {
                    "instrument": instrument,
                    "technique": technique,
                    "pitch_name_sounding": note,
                    "dynamic": dynamic,
                    "density_value": value,
                }
            )
    if not rows:
        raise LoaderError("No spectral_data rows found in nested JSON")
    return pd.DataFrame(rows)


def file_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
