"""Nonlinear Excel export tests."""

from __future__ import annotations

from pathlib import Path

from string_technique_model.extrapolation.nonlinear.domain import EvidenceTier, ExtrapolationResult, ValueKind
from string_technique_model.extrapolation.nonlinear.export_nonlinear import export_nonlinear_workbook


def test_export_workbook_sheets(tmp_path: Path) -> None:
    results = [
        ExtrapolationResult(
            record_id="r1",
            instrument="vln",
            technique="sul_ponticello",
            dynamic="pp",
            pitch="A4",
            midi=69,
            target_quantity="EWSD_score_acoustic_balanced",
            estimate_mean=12.0,
            estimate_median=12.0,
            estimate_sd=1.5,
            interval_low=9.0,
            interval_high=15.0,
            model_id="M1_hierarchical_spline",
            evidence_tier=EvidenceTier.LEVEL_2_METADATA_CONSTRAINED,
            measured_or_extrapolated="extrapolated",
            value_kind=ValueKind.EXTRAPOLATED,
            prior_dominated=True,
        )
    ]
    out = export_nonlinear_workbook(results, tmp_path / "nl.xlsx")
    assert out.exists()
    import pandas as pd

    xl = pd.ExcelFile(out)
    assert "Methodology" in xl.sheet_names
    assert "Posterior_Summary" in xl.sheet_names
    assert "Technique_Effects" in xl.sheet_names
    assert "Model_Selection" in xl.sheet_names
    assert "Model_Selection_Audit" in xl.sheet_names
    assert "Run_Summary" in xl.sheet_names
    assert "All_Results" in xl.sheet_names
