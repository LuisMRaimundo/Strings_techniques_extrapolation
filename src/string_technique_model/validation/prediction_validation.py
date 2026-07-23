"""Optional external validation against held-out technique observations.

Validation records must remain isolated from literature parameters and model fitting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from string_technique_model.config import PACKAGE_ROOT, load_yaml
from string_technique_model.literature.outputs import write_csv, write_text


def validation_enabled(pred_cfg: dict[str, Any] | None = None) -> bool:
    cfg = pred_cfg or load_yaml(PACKAGE_ROOT / "configs" / "prediction.yaml")
    block = cfg.get("validation") or {}
    return bool(block.get("enabled")) and bool(block.get("collection_ids"))


def run_prediction_validation(
    predictions: pd.DataFrame,
    observations: pd.DataFrame | None,
    *,
    output_dir: Path | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """Compute validation metrics only when enabled and observations exist."""
    if enabled is None:
        enabled = validation_enabled()
    out = Path(output_dir or PACKAGE_ROOT / "outputs" / "validation")
    reports = PACKAGE_ROOT / "reports"

    if not enabled:
        report = (
            "# Prediction validation report\n\n"
            "External validation was **not run**.\n\n"
            "`validation.enabled` is false or no validation collection IDs are configured.\n"
        )
        write_text(reports / "prediction_validation_report.md", report)
        return {"ran": False, "reason": "validation_disabled"}

    if observations is None or observations.empty:
        report = (
            "# Prediction validation report\n\n"
            "Validation enabled but no observation table was supplied.\n"
            "No claim of predictive accuracy is made.\n"
        )
        write_text(reports / "prediction_validation_report.md", report)
        return {"ran": False, "reason": "no_observations"}

    # Join on instrument, technique, pitch, dynamic
    keys = ["instrument", "technique", "pitch_midi_sounding", "dynamic"]
    merged = predictions.merge(observations, on=keys, how="inner", suffixes=("_pred", "_obs"))
    if merged.empty:
        report = "# Prediction validation report\n\nNo overlapping prediction–observation cells.\n"
        write_text(reports / "prediction_validation_report.md", report)
        return {"ran": False, "reason": "no_overlap"}

    pred = merged["estimated_density_mean"].astype(float)
    obs = merged["observed_density"].astype(float)
    mask = pred.notna() & obs.notna()
    pred = pred[mask]
    obs = obs[mask]
    err = pred - obs
    metrics = {
        "n": int(len(err)),
        "mae": float(np.mean(np.abs(err))) if len(err) else None,
        "rmse": float(np.sqrt(np.mean(err**2))) if len(err) else None,
        "median_abs_error": float(np.median(np.abs(err))) if len(err) else None,
        "bias": float(np.mean(err)) if len(err) else None,
        "pearson": float(np.corrcoef(pred, obs)[0, 1]) if len(err) > 2 else None,
        "spearman": float(pd.Series(pred).corr(pd.Series(obs), method="spearman"))
        if len(err) > 2
        else None,
    }
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "prediction_validation_metrics.csv", [metrics])
    lines = [
        "# Prediction validation report",
        "",
        "External validation **was run** on held-out observations.",
        "",
        f"- n: {metrics['n']}",
        f"- MAE: {metrics['mae']}",
        f"- RMSE: {metrics['rmse']}",
        f"- bias: {metrics['bias']}",
        "",
    ]
    write_text(reports / "prediction_validation_report.md", "\n".join(lines))
    return {"ran": True, "metrics": metrics}
