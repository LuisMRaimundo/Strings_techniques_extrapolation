"""Provenance fields survive resolver → prediction → export."""

from __future__ import annotations

from pathlib import Path

from string_technique_model.extrapolation.nonlinear.export_nonlinear import export_nonlinear_workbook
from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
    clear_harmonic_calibration_cache,
)
from string_technique_model.extrapolation.nonlinear.prediction import predict_register
from string_technique_model.extrapolation.register_builder import build_register_from_notes


def setup_function() -> None:
    clear_harmonic_calibration_cache()


def test_provenance_fields_on_viola_art_mf_results(tmp_path: Path) -> None:
    reg = build_register_from_notes("C3", "C6", "vla", "mf")
    ordinary = [
        {
            "note": r["note"],
            "midi": r["midi"],
            "value": 28.0,
            "instrument": "vla",
            "dynamic": "mf",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
            "source_path": "synthetic://vla",
            "data_status": "synthetic_integration_test",
        }
        for r in reg
    ]
    out = predict_register(
        ordinary,
        technique="artificial_harmonic",
        instrument="vla",
        dynamic="mf",
        harmonic_selection_mode="configured_physically_plausible_harmonics",
        include_low_harmonics=True,
    )
    numeric = [r for r in out if r.estimate_mean is not None]
    assert numeric
    for r in numeric:
        assert r.support_class in {
            "same_instrument_same_collection_measured",
            "same_instrument_cross_collection_measured",
        }
        assert r.source_instrument == "vla"
        assert r.source_collection
        assert r.cross_instrument_transfer_enabled is False
        assert r.source_record_ids_harmonic

    path = tmp_path / "viola_harm.xlsx"
    export_nonlinear_workbook(out, path)
    import pandas as pd

    xl = pd.ExcelFile(path)
    assert "Harmonic_Coverage" in xl.sheet_names
    assert "Harmonic_Source_Selection" in xl.sheet_names
    assert "Unsupported_Harmonic_Targets" in xl.sheet_names
    sel = pd.read_excel(path, sheet_name="Harmonic_Source_Selection")
    assert "support_class" in sel.columns
    assert "source_collection" in sel.columns
