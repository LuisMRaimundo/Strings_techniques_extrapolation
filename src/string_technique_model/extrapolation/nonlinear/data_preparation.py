"""Normalize measured rows for nonlinear extrapolation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from string_technique_model.config import PACKAGE_ROOT, resolve_path
from string_technique_model.extrapolation.baselines import normalize_instrument
from string_technique_model.extrapolation.register_builder import resolve_note
from string_technique_model.extrapolation.research_excel import (
    load_orchidea_manifest,
    parse_research_workbook,
)

_ORDINARY_TECHNIQUES = frozenset({"ordinary", "ordinario", "arco", "arco_normal", ""})
_DEFAULT_QUANTITY = "EWSD_score_acoustic_balanced"


def _normalize_technique(raw: Any) -> str:
    tech = str(raw or "ordinary").strip().lower().replace(" ", "_")
    if tech in {"", "none", "nan"}:
        return "ordinary"
    return tech


def _row_from_measured_dict(row: dict[str, Any], idx: int) -> dict[str, Any] | None:
    inst = normalize_instrument(str(row.get("instrument") or ""))
    if not inst:
        return None
    note = row.get("note") or row.get("pitch")
    if not note:
        return None
    resolved = resolve_note(str(note))
    if resolved is None:
        return None
    pitch, midi = resolved
    value = row.get("value")
    if value is None:
        value = row.get("ewsd")
    if value is None:
        return None
    try:
        value_f = float(value)
    except (TypeError, ValueError):
        return None
    return {
        "instrument": inst,
        "technique": _normalize_technique(row.get("technique")),
        "dynamic": str(row.get("dynamic") or "mf").strip().lower(),
        "note": pitch,
        "midi": int(midi),
        "value": value_f,
        "quantity": str(row.get("quantity") or _DEFAULT_QUANTITY),
        "source_path": str(row.get("source_path") or f"measured_dict_{idx}"),
    }


def normalize_measured_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert heterogeneous measured rows to a canonical dataframe."""
    normalized: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        out = _row_from_measured_dict(row, idx)
        if out is not None:
            normalized.append(out)
    return pd.DataFrame(normalized)


def filter_ordinary(df: pd.DataFrame) -> pd.DataFrame:
    """Keep ordinary / ordinario rows only."""
    if df.empty:
        return df
    tech = df["technique"].astype(str).str.lower()
    return df[tech.isin(_ORDINARY_TECHNIQUES) | tech.eq("ordinary")].copy()


def load_measured_from_orchidea_manifest(
    orchidea_root: Path | str | None = None,
    *,
    manifest_path: Path | str | None = None,
    extra_rows: list[dict[str, Any]] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Load manifest workbooks plus optional note-level measured dict rows."""
    warnings: list[str] = []
    all_rows: list[dict[str, Any]] = list(extra_rows or [])

    rows, w, _meta = load_orchidea_manifest(manifest_path, orchidea_root=orchidea_root)
    warnings.extend(w)
    for row in rows:
        all_rows.append(
            {
                "instrument": row.get("instrument"),
                "technique": "ordinary",
                "dynamic": row.get("dynamic"),
                "note": row.get("note"),
                "value": row.get("ewsd"),
                "quantity": _DEFAULT_QUANTITY,
                "source_path": row.get("source_path"),
            }
        )

    df = normalize_measured_rows(all_rows)
    if df.empty:
        warnings.append("no measured rows after normalization")
    return df, warnings


def load_measured_from_workbook(path: Path | str) -> tuple[pd.DataFrame, list[str]]:
    """Parse a single research workbook into the canonical dataframe."""
    rows, warnings = parse_research_workbook(path)
    mapped = [
        {
            "instrument": r.get("instrument"),
            "technique": "ordinary",
            "dynamic": r.get("dynamic"),
            "note": r.get("note"),
            "value": r.get("ewsd"),
            "quantity": _DEFAULT_QUANTITY,
            "source_path": r.get("source_path"),
        }
        for r in rows
    ]
    return normalize_measured_rows(mapped), warnings


def default_manifest_path() -> Path:
    return resolve_path(PACKAGE_ROOT / "configs" / "extrapolation" / "orchidea_ordinary_manifest_v1.yaml")
