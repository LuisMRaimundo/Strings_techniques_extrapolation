from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class LeakageReport:
    ok: bool
    conflicts: list[dict[str, Any]]
    message: str

    def raise_if_conflict(self) -> None:
        if not self.ok:
            raise ValueError(self.message)


def detect_calibration_validation_leakage(
    calibration: pd.DataFrame,
    validation: pd.DataFrame,
    *,
    key_cols: list[str] | None = None,
) -> LeakageReport:
    """Reject target-technique observations used in both calibration and validation."""
    if calibration is None or validation is None or calibration.empty or validation.empty:
        return LeakageReport(True, [], "No overlapping calibration/validation tables.")

    keys = key_cols or [
        "instrument",
        "technique",
        "pitch_name_sounding",
        "dynamic",
        "record_id",
        "source_file",
        "density_value",
    ]
    keys = [k for k in keys if k in calibration.columns and k in validation.columns]
    if not keys:
        return LeakageReport(True, [], "No shared key columns to compare.")

    # Focus on technique observations (exclude ordinary baselines from leakage rule
    # only when technique differs). Same target-technique rows must not appear in both.
    cal = calibration.copy()
    val = validation.copy()
    if "technique" in cal.columns:
        cal = cal[cal["technique"].astype(str) != "ordinary"]
        val = val[val["technique"].astype(str) != "ordinary"]

    if cal.empty or val.empty:
        return LeakageReport(True, [], "No target-technique overlap candidates.")

    merged = cal.merge(val, on=keys, how="inner", suffixes=("_cal", "_val"))
    if merged.empty:
        return LeakageReport(True, [], "No leakage detected.")

    conflicts = [
        {str(k): v for k, v in row.items()}
        for row in merged[keys].drop_duplicates().to_dict(orient="records")
    ]
    return LeakageReport(
        False,
        conflicts,
        "Data leakage detected: the same target-technique observations appear in both "
        f"calibration and external validation ({len(conflicts)} conflicting key rows).",
    )


def assert_role_separation(
    baseline_ids: list[str],
    calibration_ids: list[str],
    validation_ids: list[str],
) -> LeakageReport:
    cal_set = set(calibration_ids)
    val_set = set(validation_ids)
    both = sorted(cal_set & val_set)
    if both:
        return LeakageReport(
            False,
            [{"collection_id": cid, "roles": ["calibration", "validation"]} for cid in both],
            "Collections assigned simultaneously to calibration and validation: "
            + ", ".join(both),
        )
    return LeakageReport(True, [], "Collection roles are separated.")
