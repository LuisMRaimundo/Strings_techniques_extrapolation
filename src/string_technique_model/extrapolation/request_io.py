"""Column-based Measured / Requests Excel I/O for note-level extrapolation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.extrapolation.baselines import normalize_instrument

DEFAULT_IO = PACKAGE_ROOT / "configs" / "extrapolation" / "request_io_v1.yaml"


def _norm_key(s: str) -> str:
    return str(s).strip().lower().replace(" ", "_").replace("-", "_")


def load_io_config(path: Path | str | None = None) -> dict[str, Any]:
    return load_yaml(resolve_path(path or DEFAULT_IO))


def normalize_technique(label: str | None, aliases: dict[str, list[str]] | None = None) -> str | None:
    if label is None or str(label).strip() == "":
        return None
    raw = _norm_key(label)
    if aliases:
        for canon, al in aliases.items():
            if raw == _norm_key(canon) or raw in {_norm_key(a) for a in al}:
                return canon
    return raw


def _resolve_column(frame_columns: list[str], logical: str, aliases: dict[str, list[str]]) -> str | None:
    cols = {_norm_key(c): c for c in frame_columns}
    if _norm_key(logical) in cols:
        return cols[_norm_key(logical)]
    for alt in aliases.get(logical, []):
        if _norm_key(alt) in cols:
            return cols[_norm_key(alt)]
    return None


def _row_get(row: dict[str, Any], col: str | None) -> Any:
    if col is None:
        return None
    return row.get(col)


def parse_measured_table(
    frame,
    *,
    io_cfg: dict[str, Any] | None = None,
    default_instrument: str | None = None,
    default_dynamic: str | None = None,
    default_quantity: str = "EWSD_score_acoustic_balanced",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse Measured sheet/frame into registry rows."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pandas required") from exc

    cfg = io_cfg or load_io_config()
    aliases = cfg.get("aliases") or {}
    tech_aliases = cfg.get("technique_aliases") or {}
    warnings: list[str] = []

    note_c = _resolve_column(list(frame.columns), "note", aliases)
    value_c = _resolve_column(list(frame.columns), "value", aliases)
    if note_c is None or value_c is None:
        return [], ["Measured table needs columns for note and value (or EWSD_score_acoustic_balanced)"]

    inst_c = _resolve_column(list(frame.columns), "instrument", aliases)
    dyn_c = _resolve_column(list(frame.columns), "dynamic", aliases)
    tech_c = _resolve_column(list(frame.columns), "technique", aliases)
    qty_c = _resolve_column(list(frame.columns), "quantity", aliases)

    rows: list[dict[str, Any]] = []
    for i, series in frame.iterrows():
        raw = {str(k): (None if pd.isna(v) else v) for k, v in series.items()}
        note = _row_get(raw, note_c)
        val = _row_get(raw, value_c)
        if note is None or val is None:
            continue
        try:
            value = float(str(val).replace(",", "."))
        except (TypeError, ValueError):
            warnings.append(f"Measured row {i}: non-numeric value {val!r} skipped")
            continue
        inst = _row_get(raw, inst_c) or default_instrument
        dyn = _row_get(raw, dyn_c) or default_dynamic
        tech = normalize_technique(_row_get(raw, tech_c), tech_aliases) or "ordinary"
        qty = _row_get(raw, qty_c) or default_quantity
        if inst is None or dyn is None:
            warnings.append(f"Measured note {note}: missing instrument/dynamic")
            continue
        rows.append(
            {
                "note": str(note).strip(),
                "value": value,
                "instrument": normalize_instrument(str(inst)),
                "dynamic": str(dyn).strip().lower(),
                "technique": tech,
                "quantity": str(qty).strip(),
                "metadata": {k: v for k, v in raw.items() if k not in {note_c, value_c}},
                "row_index": int(i) if isinstance(i, int) else i,
            }
        )
    if not rows:
        warnings.append("No usable measured rows parsed")
    return rows, warnings


def parse_request_table(
    frame,
    *,
    io_cfg: dict[str, Any] | None = None,
    default_instrument: str | None = None,
    default_dynamic: str | None = None,
    default_quantity: str = "EWSD_score_acoustic_balanced",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse Requests sheet/frame: note names you need + technique."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pandas required") from exc

    cfg = io_cfg or load_io_config()
    aliases = cfg.get("aliases") or {}
    tech_aliases = cfg.get("technique_aliases") or {}
    warnings: list[str] = []

    note_c = _resolve_column(list(frame.columns), "note", aliases)
    tech_c = _resolve_column(list(frame.columns), "technique", aliases)
    if note_c is None or tech_c is None:
        return [], ["Requests table needs columns for note and technique"]

    inst_c = _resolve_column(list(frame.columns), "instrument", aliases)
    dyn_c = _resolve_column(list(frame.columns), "dynamic", aliases)
    qty_c = _resolve_column(list(frame.columns), "quantity", aliases)

    rows: list[dict[str, Any]] = []
    for i, series in frame.iterrows():
        raw = {str(k): (None if pd.isna(v) else v) for k, v in series.items()}
        note = _row_get(raw, note_c)
        tech_raw = _row_get(raw, tech_c)
        if note is None or tech_raw is None:
            continue
        tech = normalize_technique(str(tech_raw), tech_aliases)
        if tech is None:
            warnings.append(f"Request row {i}: unknown technique {tech_raw!r}")
            continue
        inst = _row_get(raw, inst_c) or default_instrument
        dyn = _row_get(raw, dyn_c) or default_dynamic
        qty = _row_get(raw, qty_c) or default_quantity
        rows.append(
            {
                "note": str(note).strip(),
                "technique": tech,
                "instrument": normalize_instrument(str(inst)) if inst else None,
                "dynamic": str(dyn).strip().lower() if dyn else None,
                "quantity": str(qty).strip(),
                "metadata": raw,
                "row_index": int(i) if isinstance(i, int) else i,
            }
        )
    if not rows:
        warnings.append("No usable request rows parsed")
    return rows, warnings


def load_request_workbook(
    path: Path | str,
    *,
    measured_sheet: str = "Measured",
    request_sheet: str = "Requests",
    default_instrument: str | None = None,
    default_dynamic: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Load a workbook with Measured + Requests sheets (or first two sheets)."""
    import pandas as pd

    path = Path(path)
    xl = pd.ExcelFile(path)
    sheets = xl.sheet_names
    m_sheet = measured_sheet if measured_sheet in sheets else sheets[0]
    r_sheet = request_sheet if request_sheet in sheets else (sheets[1] if len(sheets) > 1 else sheets[0])
    warnings: list[str] = []
    if m_sheet == r_sheet and len(sheets) == 1:
        warnings.append("Only one sheet found; expecting separate Measured and Requests sheets")
    measured, w1 = parse_measured_table(
        xl.parse(m_sheet),
        default_instrument=default_instrument,
        default_dynamic=default_dynamic,
    )
    requests, w2 = parse_request_table(
        xl.parse(r_sheet),
        default_instrument=default_instrument,
        default_dynamic=default_dynamic,
    )
    warnings.extend(w1)
    warnings.extend(w2)
    warnings.append(f"sheets used: Measured={m_sheet!r}, Requests={r_sheet!r}")
    return measured, requests, warnings


def write_request_template(path: Path | str) -> Path:
    """Write an empty Measured/Requests Excel template for the user."""
    import pandas as pd

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    measured = pd.DataFrame(
        [
            {
                "note": "A4",
                "value": 67.0,
                "instrument": "vla",
                "dynamic": "pp",
                "technique": "ordinary",
                "quantity": "EWSD_score_acoustic_balanced",
                "source": "example",
            },
            {
                "note": "G3",
                "value": 55.0,
                "instrument": "vla",
                "dynamic": "pp",
                "technique": "ordinary",
                "quantity": "EWSD_score_acoustic_balanced",
                "source": "example",
            },
        ]
    )
    requests = pd.DataFrame(
        [
            {"note": "A4", "technique": "con_sordino", "instrument": "vla", "dynamic": "pp"},
            {"note": "A4", "technique": "sul_tasto", "instrument": "vla", "dynamic": "pp"},
            {"note": "A4", "technique": "sul_ponticello", "instrument": "vla", "dynamic": "pp"},
            {"note": "A4", "technique": "artificial_harmonic", "instrument": "vla", "dynamic": "pp"},
            {"note": "G3", "technique": "sul_tasto", "instrument": "vla", "dynamic": "pp"},
        ]
    )
    readme = pd.DataFrame(
        {
            "instruction": [
                "Sheet Measured = notes you HAVE (note + value/EWSD + metadata).",
                "Sheet Requests = notes you NEED + technique (sul_tasto, sul_ponticello, con_sordino, ...).",
                "The engine looks up each Request.note in Measured (same instrument/dynamic), then applies literature effects.",
                "If literature cannot justify a numeric EWSD for that technique, value is NA with reason; baseline is still returned.",
                "You can also load a Spectral_Analyser compiled_density_metrics_research.xlsx as Measured via CLI/GUI import.",
            ]
        }
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        measured.to_excel(writer, sheet_name="Measured", index=False)
        requests.to_excel(writer, sheet_name="Requests", index=False)
        readme.to_excel(writer, sheet_name="README", index=False)
    return path
