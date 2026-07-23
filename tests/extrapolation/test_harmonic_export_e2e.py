"""End-to-end: harmonic unavailable rows must survive Excel export."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from string_technique_model.extrapolation.nonlinear import export_nonlinear_workbook, predict_register
from string_technique_model.extrapolation.register_builder import build_register_from_notes


def _ordinary() -> list[dict]:
    reg = build_register_from_notes("G3", "G7", "vln", "ff")
    return [
        {
            "note": r["note"],
            "midi": r["midi"],
            "value": 40.0 * (0.985**i),
            "instrument": "vln",
            "dynamic": "ff",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
            "source_path": f"synthetic_integration_test://{r['note']}",
            "data_status": "synthetic_integration_test",
        }
        for i, r in enumerate(reg)
    ]


def test_export_retains_unavailable_harmonics(tmp_path: Path) -> None:
    rows = _ordinary()
    all_r = []
    for tech in (
        "con_sordino",
        "sul_tasto",
        "sul_ponticello",
        "artificial_harmonic",
        "natural_harmonic",
    ):
        all_r.extend(
            predict_register(
                rows,
                technique=tech,
                instrument="vln",
                dynamic="ff",
                harmonic_selection_mode="configured_physically_plausible_harmonics",
                harmonic_sounding_max="C8",
                include_low_harmonics=True,
            )
        )
    assert any(r.technique == "natural_harmonic" for r in all_r)
    assert any(r.technique == "artificial_harmonic" for r in all_r)
    n_unavail = sum(1 for r in all_r if r.value_kind.value == "unavailable")
    assert n_unavail > 0

    out = export_nonlinear_workbook(
        all_r,
        tmp_path / "e2e_harmonics.xlsx",
        run_metadata={"requested_method": "automatic"},
    )
    xl = pd.ExcelFile(out)
    all_df = pd.read_excel(out, sheet_name="All_Results")
    un_df = pd.read_excel(out, sheet_name="Unavailable")
    run = pd.read_excel(out, sheet_name="Run_Summary")
    keys = dict(zip(run["key"].astype(str), run["value"].astype(str)))

    counts = all_df["technique"].value_counts().to_dict()
    assert counts.get("con_sordino") == 49
    assert counts.get("sul_tasto") == 49
    assert counts.get("sul_ponticello") == 49
    assert counts.get("artificial_harmonic", 0) > 0
    assert counts.get("natural_harmonic", 0) > 0
    assert int(keys["n_results"]) == len(all_df) == len(all_r)
    assert int(keys["n_unavailable"]) == len(un_df) == n_unavail
    assert int(keys["n_numeric_results"]) == 147
    assert "artificial_harmonic" in keys["techniques_exported"]
    assert "natural_harmonic" in keys["techniques_exported"]

    # Unavailable sheet must not be header-only
    assert len(un_df) >= counts["artificial_harmonic"] + counts["natural_harmonic"]

    nat = all_df[all_df["technique"] == "natural_harmonic"]
    assert nat["string_name"].notna().any() or nat["open_string_pitch"].notna().any()
    assert nat["harmonic_order"].notna().all()
    assert nat["sounding_frequency_hz"].notna().all()
    assert nat["cents_deviation"].notna().any()
    assert (nat["model_status"] == "modal_frequencies_generated_acoustic_values_unavailable").all()
    assert (nat["fallback_level"] == "no_numeric_fallback").all()
    assert (nat["complexity_level"] == "not_applicable").all()
    assert (nat["extrapolation_method"] == "harmonic_modal_acoustic_model_unavailable").all()
    assert (nat["na_reason"] == "no_harmonic_acoustic_calibration_data").all()
    assert nat["selection_mode"].notna().all()
    assert (nat["configured_order_min"] == 2).all()
    assert (nat["order_selection_reason"] == "practical_analysis_scope").all()

    art = all_df[all_df["technique"] == "artificial_harmonic"]
    assert art["selection_mode"].notna().all()
    assert (art["configuration_policy"] == "canonical_single_string_assignment").all()

    # Physical range includes below C6 (e.g. G4 from G3×2)
    from string_technique_model.extrapolation.register_builder import resolve_note

    midis = []
    for p in nat["sounding_pitch"].astype(str):
        rn = resolve_note(p)
        if rn:
            midis.append(rn[1])
    assert midis and min(midis) < 84  # below C6

    assert "Model_Selection_Audit" in xl.sheet_names
    audit = pd.read_excel(out, sheet_name="Model_Selection_Audit")
    assert (audit["technique"] == "natural_harmonic").any()
    assert (audit["technique"] == "artificial_harmonic").any()
    sel = pd.read_excel(out, sheet_name="Model_Selection")
    harm_sel = sel[sel["technique"].isin(["natural_harmonic", "artificial_harmonic"])]
    assert (harm_sel["selected_model_id"] == "harmonic_modal_acoustic_model_unavailable").all()
    # After enrichment, modal covariates are available; calibration is a model component
    for _, row in harm_sel.iterrows():
        avail = str(row.get("available_covariates") or "")
        missing = str(row.get("missing_covariates") or "")
        missing_comp = str(row.get("missing_model_components") or "")
        assert "harmonic_order" in avail or "string" in avail
        assert "calibrated_harmonic_descriptor_model" not in missing
        assert "calibrated_harmonic_descriptor_model" in missing_comp
        assert str(row.get("modal_metadata_status") or "") == "complete"
        assert str(row.get("acoustic_calibration_status") or "") == "unavailable"
        assert "beta" not in missing
    audit_harm = audit[audit["technique"].isin(["natural_harmonic", "artificial_harmonic"])]
    gate = audit_harm[audit_harm["model_id"] == "harmonic_modal_metadata_gate"]
    assert not gate.empty
    assert (gate["rejection_reason"] == "gate_not_applicable_modal_metadata_complete").all()
    assert "failed_requirement:harmonic_metadata_complete" not in set(gate["rejection_reason"])
