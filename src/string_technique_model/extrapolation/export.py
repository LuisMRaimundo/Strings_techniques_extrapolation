"""Auditable Excel export for narrow extrapolation results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.extrapolation.models import ExtrapolationCell

OUTPUT_COLUMNS = [
    "instrument",
    "technique",
    "dynamic",
    "target_quantity",
    "value",
    "lower_bound",
    "upper_bound",
    "unit",
    "value_kind",
    "evidence_status",
    "source",
    "source_page",
    "measurement_domain",
    "extrapolation_method",
    "baseline_record_ids",
    "uncertainty",
    "measured_or_extrapolated",
    "assumptions_used",
    "warnings",
    "mute_state",
    "evidence_id",
    "baseline_ewsd_mean",
    "na_reason",
]


def cells_to_rows(cells: list[ExtrapolationCell]) -> list[dict[str, Any]]:
    rows = []
    for c in cells:
        row = c.to_row()
        rows.append({k: row.get(k) for k in OUTPUT_COLUMNS})
    return rows


def export_extrapolation_workbook(
    result: dict[str, Any],
    path: Path | str,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pandas required for Excel export") from exc

    cells: list[ExtrapolationCell] = result["cells"]
    summary = result.get("summary") or {}
    rows = cells_to_rows(cells)
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)

    summary_frame = pd.DataFrame(
        [{"key": k, "value": str(v)} for k, v in summary.items()]
        + [
            {
                "key": "policy",
                "value": (
                    "EWSD_score_acoustic_balanced not numerically extrapolated; "
                    "component tendencies and instrument-specific mute attenuation only."
                ),
            }
        ]
    )

    # Audit sheets
    measured = frame[frame["value_kind"] == "measured"]
    lit = frame[frame["value_kind"] == "literature_bounded"]
    qual = frame[frame["value_kind"] == "qualitative_only"]
    na = frame[frame["value_kind"] == "unavailable"]

    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            frame.to_excel(writer, sheet_name="Extrapolation_Results", index=False)
            summary_frame.to_excel(writer, sheet_name="Run_Summary", index=False)
            measured.to_excel(writer, sheet_name="Measured_Baseline", index=False)
            lit.to_excel(writer, sheet_name="Literature_Bounded", index=False)
            qual.to_excel(writer, sheet_name="Qualitative_Only", index=False)
            na.to_excel(writer, sheet_name="Unavailable_NA", index=False)
    except Exception:
        # Fallback CSV bundle if openpyxl missing
        csv_path = path.with_suffix(".csv")
        frame.to_csv(csv_path, index=False)
        summary_path = path.with_name(path.stem + "_summary.csv")
        summary_frame.to_csv(summary_path, index=False)
        return csv_path

    return path
