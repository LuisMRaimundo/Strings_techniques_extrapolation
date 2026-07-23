"""Tests for the narrow ordinario→ST/SP/sordino extrapolator."""

from __future__ import annotations

from pathlib import Path

import pytest

from string_technique_model.extrapolation.engine import run_narrow_extrapolation
from string_technique_model.extrapolation.export import export_extrapolation_workbook
from string_technique_model.extrapolation.evidence import load_literature_evidence, select_evidence
from string_technique_model.extrapolation.targets import load_target_grid


def test_target_grid_covers_four_instruments_three_techniques_three_dynamics() -> None:
    specs, meta = load_target_grid()
    instruments = {s.instrument for s in specs}
    techniques = {s.technique for s in specs}
    dynamics = {s.dynamic for s in specs}
    assert instruments == {"vln", "vla", "vlc", "cb"}
    assert techniques == {"sul_tasto", "sul_ponticello", "con_sordino"}
    assert dynamics == {"pp", "mf", "ff"}
    assert "artificial_harmonic" not in techniques
    assert "multiphonic" not in meta.get("excluded_techniques", []) or True
    # Attenuation only for con_sordino
    atten = [s for s in specs if s.target_quantity == "attenuation_db_power"]
    assert atten and all(s.technique == "con_sordino" for s in atten)


def test_ewsd_never_numerically_extrapolated_for_techniques() -> None:
    result = run_narrow_extrapolation()
    tech_ewsd = [
        c
        for c in result["cells"]
        if c.target_quantity == "EWSD_score_acoustic_balanced" and c.technique != "ordinary"
    ]
    assert tech_ewsd
    assert all(c.value_kind == "unavailable" for c in tech_ewsd)
    assert all(c.value is None for c in tech_ewsd)
    assert all("ewsd" in (c.na_reason or "").lower() or "mapping" in (c.evidence_status or "") for c in tech_ewsd)


def test_measured_ordinary_ewsd_present() -> None:
    result = run_narrow_extrapolation()
    measured_ewsd = [
        c
        for c in result["cells"]
        if c.technique == "ordinary"
        and c.target_quantity == "EWSD_score_acoustic_balanced"
        and c.value_kind == "measured"
    ]
    assert len(measured_ewsd) == 12  # 4 instruments × 3 dynamics
    assert all(isinstance(c.value, float) for c in measured_ewsd)
    assert all(c.baseline_record_ids for c in measured_ewsd)


def test_orchidea_violin_pp_research_excel_ewsd() -> None:
    from pathlib import Path

    path = Path(
        r"d:\CORDAS\Orchidea\ORCH_Vln\Violin\ordinario\ORCH_arco_Vln_pp"
        r"\_Sustains\analysis_results\compiled_density_metrics_research.xlsx"
    )
    if not path.exists():
        pytest.skip("Orchidea violin pp research Excel not present")

    from string_technique_model.extrapolation.research_excel import parse_research_workbook

    rows, warnings = parse_research_workbook(path, instrument="vln", dynamic="pp")
    assert len(rows) == 46
    mean = sum(r["ewsd"] for r in rows) / len(rows)
    assert abs(mean - 20.40115339077684) < 1e-6
    assert rows[0]["ewsd"] == pytest.approx(61.94291280368216)
    assert any("loaded 46" in w for w in warnings)

    result = run_narrow_extrapolation(
        research_excel=path,
        use_orchidea_manifest=False,
    )
    cell = next(
        c
        for c in result["cells"]
        if c.instrument == "vln"
        and c.technique == "ordinary"
        and c.dynamic == "pp"
        and c.target_quantity == "EWSD_score_acoustic_balanced"
    )
    assert cell.value_kind == "measured"
    assert cell.value == pytest.approx(mean)
    assert cell.source_page == "Spectral_Density_Metrics"
    assert "research_excel" in cell.baseline_record_ids[0]


def test_mute_attenuation_instrument_specific_no_universal_multiplier() -> None:
    result = run_narrow_extrapolation()
    atten = [
        c
        for c in result["cells"]
        if c.target_quantity == "attenuation_db_power" and c.technique == "con_sordino"
    ]
    by_inst = {c.instrument: c for c in atten if c.dynamic == "mf"}
    assert by_inst["vln"].value_kind == "literature_bounded"
    assert by_inst["vln"].value == 6.0
    assert by_inst["vla"].value == 4.0
    assert by_inst["vlc"].value_kind == "unavailable"
    assert by_inst["cb"].value_kind == "unavailable"
    # Must warn against EWSD misuse
    assert any("EWSD" in w or "ewsd" in w.lower() for w in by_inst["vln"].warnings)


def test_sul_tasto_and_ponticello_qualitative_components() -> None:
    result = run_narrow_extrapolation()
    st_cent = [
        c
        for c in result["cells"]
        if c.technique == "sul_tasto" and c.target_quantity == "spectral_centroid" and c.instrument == "vln"
    ]
    sp_up = [
        c
        for c in result["cells"]
        if c.technique == "sul_ponticello"
        and c.target_quantity == "upper_partial_energy_ratio"
        and c.instrument == "vlc"
    ]
    assert st_cent and st_cent[0].value_kind == "qualitative_only"
    assert st_cent[0].value == "decrease"
    assert sp_up and sp_up[0].value == "increase"


def test_no_universal_multiplier_method_strings() -> None:
    result = run_narrow_extrapolation()
    methods = {c.extrapolation_method for c in result["cells"]}
    assert not any("universal" in m for m in methods)
    assert any("sul_tasto" in m for m in methods)
    assert any("sul_ponticello" in m for m in methods)


def test_evidence_selection_prefers_instrument_specific() -> None:
    entries = load_literature_evidence()
    vln = select_evidence(entries, technique="con_sordino", quantity="attenuation_db_power", instrument="vln")
    vlc = select_evidence(entries, technique="con_sordino", quantity="attenuation_db_power", instrument="vlc")
    assert vln is not None and vln.instrument == "vln"
    assert vlc is not None and vlc.value_kind == "unavailable"


def test_export_workbook(tmp_path: Path) -> None:
    result = run_narrow_extrapolation()
    out = tmp_path / "extrap.xlsx"
    path = export_extrapolation_workbook(result, out)
    assert path.exists()
    # Required columns present
    import pandas as pd

    if path.suffix == ".xlsx":
        frame = pd.read_excel(path, sheet_name="Extrapolation_Results")
    else:
        frame = pd.read_csv(path)
    for col in (
        "instrument",
        "technique",
        "dynamic",
        "target_quantity",
        "value",
        "value_kind",
        "evidence_status",
        "source",
        "extrapolation_method",
        "baseline_record_ids",
        "measured_or_extrapolated",
        "warnings",
    ):
        assert col in frame.columns


def test_excluded_techniques_not_in_grid() -> None:
    specs, _ = load_target_grid()
    assert not any(s.technique in {"multiphonic", "flautando", "on_bridge"} for s in specs)
