"""Ingest Spectral_Analyser compiled_density_metrics_research.xlsx as measured baselines."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.extrapolation.baselines import normalize_instrument

DEFAULT_MANIFEST = PACKAGE_ROOT / "configs" / "extrapolation" / "orchidea_ordinary_manifest_v1.yaml"

_INSTRUMENT_FROM_LABEL = {
    "violin": "vln",
    "viola": "vla",
    "cello": "vlc",
    "violoncello": "vlc",
    "contrabass": "cb",
    "double bass": "cb",
    "double_bass": "cb",
    "bass": "cb",
}

# Columns optionally averaged as measured ordinary components
_COMPONENT_ALIASES = {
    "spectral_slope": ("spectral_slope_db_per_harmonic",),
    "upper_partial_energy_ratio": (
        "brightness_or_upper_spectral_activity_index_20khz",
        "high_frequency_spectral_activity_sum",
    ),
}


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
        if not value:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _infer_instrument(frame_row: dict[str, Any], path: Path, declared: str | None) -> str | None:
    if declared:
        return normalize_instrument(declared)
    for key in ("Instrument", "instrument"):
        if key in frame_row and frame_row[key] is not None:
            label = str(frame_row[key]).strip().lower()
            if label in _INSTRUMENT_FROM_LABEL:
                return _INSTRUMENT_FROM_LABEL[label]
            return normalize_instrument(label)
    parts = " ".join(path.parts).lower()
    for token, code in (
        ("orch_vln", "vln"),
        ("violin", "vln"),
        ("orch_vla", "vla"),
        ("viola", "vla"),
        ("orch_vlc", "vlc"),
        ("violoncello", "vlc"),
        ("cello", "vlc"),
        ("orch_cb", "cb"),
        ("contrabass", "cb"),
        ("double_bass", "cb"),
    ):
        if token in parts:
            return code
    return None


def _infer_dynamic(frame_row: dict[str, Any], path: Path, declared: str | None) -> str | None:
    if declared:
        return str(declared).strip().lower()
    for key in ("Dynamic", "dynamic"):
        if key in frame_row and frame_row[key] is not None:
            return str(frame_row[key]).strip().lower()
    parts = path.as_posix().lower()
    for dyn in ("ppp", "pp", "mp", "mf", "ff", "f"):
        if f"_{dyn}" in parts or f"-{dyn}" in parts or f"/{dyn}/" in parts or parts.endswith(dyn):
            # Prefer longer tokens first already ordered loosely; avoid matching 'f' inside 'ff'
            if dyn == "f" and ("_ff" in parts or "-ff" in parts or "_mf" in parts):
                continue
            return dyn
    return None


def parse_research_workbook(
    path: Path | str,
    *,
    sheet_name: str = "Spectral_Density_Metrics",
    ewsd_column: str = "EWSD_score_acoustic_balanced",
    instrument: str | None = None,
    dynamic: str | None = None,
    component_map: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse one research Excel into measured note rows.

    Returns (rows, warnings). Each row has instrument, dynamic, note, ewsd, components, source_path.
    """
    path = Path(path)
    warnings: list[str] = []
    try:
        import pandas as pd
    except ImportError:
        return [], ["pandas unavailable"]

    if not path.exists():
        return [], [f"missing research Excel: {path}"]

    try:
        xl = pd.ExcelFile(path)
    except Exception as exc:  # noqa: BLE001
        return [], [f"could not open {path}: {exc}"]

    sheet = sheet_name if sheet_name in xl.sheet_names else None
    if sheet is None:
        for candidate in xl.sheet_names:
            if "density" in candidate.lower() or "ewsd" in candidate.lower():
                sheet = candidate
                break
    if sheet is None:
        return [], [f"no Spectral_Density_Metrics-like sheet in {path.name}"]

    frame = xl.parse(sheet)
    if ewsd_column not in frame.columns:
        # case-insensitive fallback
        cols = {str(c).lower(): c for c in frame.columns}
        if ewsd_column.lower() in cols:
            ewsd_column = cols[ewsd_column.lower()]
        else:
            return [], [f"{path.name}: missing column {ewsd_column!r}"]

    comp_cols: dict[str, str] = {}
    if component_map:
        for qty, col in component_map.items():
            if col in frame.columns:
                comp_cols[qty] = col
    else:
        for qty, aliases in _COMPONENT_ALIASES.items():
            for col in aliases:
                if col in frame.columns:
                    comp_cols[qty] = col
                    break

    rows: list[dict[str, Any]] = []
    for _, series in frame.iterrows():
        raw = {str(k): (None if pd.isna(v) else v) for k, v in series.items()}
        ewsd = _coerce_float(raw.get(ewsd_column))
        if ewsd is None:
            continue
        inst = _infer_instrument(raw, path, instrument)
        dyn = _infer_dynamic(raw, path, dynamic)
        note = raw.get("Note") or raw.get("note")
        if inst is None or dyn is None:
            warnings.append(f"{path.name}: skipped note={note!r} (instrument/dynamic unresolved)")
            continue
        components = {qty: _coerce_float(raw.get(col)) for qty, col in comp_cols.items()}
        rows.append(
            {
                "instrument": normalize_instrument(inst),
                "dynamic": str(dyn).lower(),
                "note": str(note) if note is not None else None,
                "ewsd": ewsd,
                "components": components,
                "source_path": str(path),
                "sheet": sheet,
                "ewsd_column": ewsd_column,
                "ci_low": _coerce_float(raw.get("EWSD_score_acoustic_balanced_ci_low")),
                "ci_high": _coerce_float(raw.get("EWSD_score_acoustic_balanced_ci_high")),
            }
        )
    if not rows:
        warnings.append(f"{path.name}: no usable EWSD rows")
    else:
        warnings.append(f"loaded {len(rows)} measured EWSD rows from {path}")
    return rows, warnings


def load_orchidea_manifest(
    manifest_path: Path | str | None = None,
    *,
    orchidea_root: Path | str | None = None,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """Load all ordinary workbooks listed in the manifest."""
    data = load_yaml(resolve_path(manifest_path or DEFAULT_MANIFEST))
    root = Path(orchidea_root or data.get("default_orchidea_root") or "")
    sheet = data.get("sheet_name") or "Spectral_Density_Metrics"
    ewsd_col = data.get("ewsd_column") or "EWSD_score_acoustic_balanced"
    component_map = data.get("component_columns") or {}
    # normalize component_columns values to quantity→excel_col for spectral_slope etc.
    # manifest uses spectral_slope: spectral_slope_db_per_harmonic
    all_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    loaded: list[str] = []
    missing: list[str] = []

    for entry in data.get("workbooks") or []:
        rel = entry.get("relative_path") or entry.get("path")
        if not rel:
            continue
        path = Path(rel)
        if not path.is_absolute():
            path = root / rel
        if not path.exists():
            missing.append(str(path))
            warnings.append(f"manifest missing: {path}")
            continue
        rows, w = parse_research_workbook(
            path,
            sheet_name=sheet,
            ewsd_column=ewsd_col,
            instrument=entry.get("instrument"),
            dynamic=entry.get("dynamic"),
            component_map={
                # remap proxy name used in manifest
                ("upper_partial_energy_ratio" if k == "upper_partial_energy_proxy" else k): v
                for k, v in component_map.items()
            },
        )
        warnings.extend(w)
        all_rows.extend(rows)
        loaded.append(str(path))

    meta = {
        "loaded_paths": loaded,
        "missing_paths": missing,
        "n_rows": len(all_rows),
        "orchidea_root": str(root),
        "manifest": str(resolve_path(manifest_path or DEFAULT_MANIFEST)),
    }
    return all_rows, warnings, meta
