"""Prediction output writers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from string_technique_model.literature.outputs import write_csv

PREDICTION_COLUMNS = [
    "prediction_id",
    "baseline_cell_id",
    "baseline_run_id",
    "instrument",
    "technique",
    "pitch_name_written",
    "pitch_midi_written",
    "pitch_name_sounding",
    "pitch_midi_sounding",
    "dynamic",
    "string_name",
    "harmonic_order",
    "stopped_pitch",
    "touched_pitch",
    "mute_type",
    "bow_position_ratio",
    "baseline_density",
    "estimated_density_mean",
    "estimated_density_median",
    "estimated_density_sd",
    "estimated_density_q025",
    "estimated_density_q050",
    "estimated_density_q975",
    "probability_above_ordinary",
    "probability_below_ordinary",
    "difference_from_ordinary_mean",
    "ratio_to_ordinary_median",
    "modelling_backend",
    "link_function",
    "active_parameter_ids",
    "inactive_parameter_ids",
    "evidence_source_ids",
    "evidence_extract_ids",
    "evidence_grade",
    "reliability_class",
    "transfer_used",
    "transfer_source_instrument",
    "applicability_status",
    "prediction_status",
    "metric_mapping_status",
    "numerical_safeguard_applied",
    "measured_or_estimated",
    "result_basis",
    "literature_validated",
    "evidence_based",
    "assumption_ids_used",
    "result_status",
    "assumption_status",
    "assumptions_used",
    "calculation_trace",
    "warnings",
    "provenance",
    "random_seed",
    "model_version",
    "parameter_ledger_version",
    "created_at_utc",
]


def write_prediction_outputs(
    rows: list[dict[str, Any]],
    parameter_ledger_rows: list[dict[str, Any]],
    mechanism_rows: list[dict[str, Any]],
    *,
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    df = pd.DataFrame(rows)
    for col in PREDICTION_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[PREDICTION_COLUMNS]
    csv_path = output_dir / "technique_predictions.csv"
    pq_path = output_dir / "technique_predictions.parquet"
    df.to_csv(csv_path, index=False)
    try:
        from string_technique_model.io import check_parquet_engine

        preflight = check_parquet_engine()
        if not preflight.ok:
            files["technique_predictions.parquet"] = ""
            files["parquet_warning"] = (
                f"Parquet unavailable ({preflight.error_message}); "
                f"CSV written instead. {preflight.actionable_hint}"
            )
        else:
            df.to_parquet(pq_path, index=False)
            files["technique_predictions.parquet"] = str(pq_path)
    except Exception as exc:  # noqa: BLE001
        files["technique_predictions.parquet"] = ""
        files["parquet_warning"] = f"Parquet write failed ({exc}); CSV written instead."
    files["technique_predictions.csv"] = str(csv_path)
    files["prediction_parameter_ledger.csv"] = write_csv(
        output_dir / "prediction_parameter_ledger.csv", parameter_ledger_rows
    )
    files["mechanism_only_constraints.csv"] = write_csv(
        output_dir / "mechanism_only_constraints.csv", mechanism_rows
    )
    return files


def prediction_summary_markdown(rows: list[dict[str, Any]]) -> str:
    n = len(rows)
    n_na = sum(1 for r in rows if r.get("estimated_density_mean") is None)
    n_est = n - n_na
    lines = [
        "# Technique prediction summary",
        "",
        f"- rows: {n}",
        f"- numerical estimates: {n_est}",
        f"- NA / non-estimable: {n_na}",
        "",
        "Estimates are modelled, never measured.",
        "",
    ]
    return "\n".join(lines)
