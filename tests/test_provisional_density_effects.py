"""Provisional numeric density estimates from ordinary baselines."""

from __future__ import annotations

from string_technique_model.extrapolation.density_effects import estimate_technique_density
from string_technique_model.extrapolation.note_level import run_note_level_requests


def test_mute_violin_scales_by_power_db() -> None:
    # 6 dB → × 10^(-0.6) ≈ 0.2512
    est = estimate_technique_density(
        baseline=70.623528,
        technique="con_sordino",
        instrument="vln",
        literature_atten_db=6.0,
    )
    assert est is not None
    assert est["value_kind"] == "extrapolated"
    assert abs(est["value"] - 70.623528 * (10 ** (-0.6))) < 1e-6
    assert est["lower_bound"] < est["value"] < est["upper_bound"]


def test_sul_tasto_decreases_sul_pont_increases() -> None:
    base = 40.0
    st = estimate_technique_density(baseline=base, technique="sul_tasto", instrument="vla")
    sp = estimate_technique_density(baseline=base, technique="sul_ponticello", instrument="vla")
    assert st["value"] < base
    assert sp["value"] > base


def test_results_grouped_by_technique_not_interleaved() -> None:
    measured = [
        {
            "note": n,
            "value": 50.0 + i,
            "instrument": "vln",
            "dynamic": "pp",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
        }
        for i, n in enumerate(["G3", "A3", "B3"])
    ]
    requests = [
        {
            "note": n,
            "technique": t,
            "instrument": "vln",
            "dynamic": "pp",
            "quantity": "EWSD_score_acoustic_balanced",
        }
        for n in ("G3", "A3", "B3")
        for t in ("sul_tasto", "con_sordino", "sul_ponticello")
    ]
    result = run_note_level_requests(measured, requests)
    techs = [r["request_technique"] for r in result["results"]]
    # All con_sordino first, then sul_tasto, then sul_ponticello
    assert techs == (
        ["con_sordino"] * 3 + ["sul_tasto"] * 3 + ["sul_ponticello"] * 3
    )


def test_export_has_technique_sheets(tmp_path) -> None:
    import pandas as pd

    from string_technique_model.extrapolation.note_level import export_note_level_workbook

    measured = [
        {
            "note": "G3",
            "value": 70.0,
            "instrument": "vln",
            "dynamic": "pp",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
        }
    ]
    requests = [
        {
            "note": "G3",
            "technique": t,
            "instrument": "vln",
            "dynamic": "pp",
            "quantity": "EWSD_score_acoustic_balanced",
        }
        for t in ("con_sordino", "sul_tasto")
    ]
    result = run_note_level_requests(measured, requests)
    out = export_note_level_workbook(result, tmp_path / "out.xlsx")
    xl = pd.ExcelFile(out)
    assert "All_Results" in xl.sheet_names
    assert "con_sordino" in xl.sheet_names
    assert "sul_tasto" in xl.sheet_names


def test_note_level_returns_numeric_for_g3() -> None:
    measured = [
        {
            "note": "G3",
            "value": 70.623528,
            "instrument": "vln",
            "dynamic": "pp",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
        }
    ]
    requests = [
        {"note": "G3", "technique": t, "instrument": "vln", "dynamic": "pp", "quantity": "EWSD_score_acoustic_balanced"}
        for t in ("sul_tasto", "sul_ponticello", "con_sordino", "artificial_harmonic")
    ]
    result = run_note_level_requests(measured, requests)
    assert result["summary"]["n_numeric_value"] == 4
    by = {r["request_technique"]: r for r in result["results"]}
    assert by["con_sordino"]["value"] is not None
    assert by["con_sordino"]["baseline_value"] == 70.623528
    assert by["sul_tasto"]["value"] < 70.623528
    assert by["sul_ponticello"]["value"] > 70.623528
