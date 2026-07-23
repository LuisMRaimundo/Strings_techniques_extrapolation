"""Integration coverage for all major model-selection branches."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from string_technique_model.extrapolation.nonlinear.export_nonlinear import export_nonlinear_workbook
from string_technique_model.extrapolation.nonlinear.model_selection import (
    DataAvailability,
    select_model,
)
from string_technique_model.extrapolation.nonlinear.prediction import predict_register
from string_technique_model.extrapolation.register_builder import build_register_from_notes


def _ordinary(n_notes: int = 20, dynamic: str = "mf") -> list[dict]:
    reg = build_register_from_notes("G3", "G7", "vln", dynamic)[:n_notes]
    return [
        {
            "note": r["note"],
            "midi": r["midi"],
            "value": 30.0 * (0.98**i),
            "instrument": "vln",
            "dynamic": dynamic,
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
            "source_path": f"synthetic://ord/{r['note']}",
        }
        for i, r in enumerate(reg)
    ]


def test_branch_zero_obs_bow_constant() -> None:
    d = select_model(
        DataAvailability(
            technique="sul_ponticello",
            instrument="vln",
            dynamic="mf",
            target_quantity="EWSD_score_acoustic_balanced",
            n_target_observations=0,
            missing_covariates=["beta", "bow_force", "bow_velocity"],
        )
    )
    assert d.selected_model_id == "constant_technique_effect_over_smoothed_baseline"
    assert d.model_selection_status == "completed_assumption_fallback"
    assert "physical_informed_bow_contact" in d.rejected_model_ids


def test_branch_linear_vs_spline() -> None:
    linear = select_model(
        DataAvailability(
            technique="sul_tasto",
            instrument="vln",
            dynamic="pp",
            target_quantity="spectral_centroid",
            n_target_observations=4,
            distinct_pitch_count=4,
            pitch_span_semitones=8,
            spline_design_is_identifiable=False,
            missing_covariates=["beta"],
        )
    )
    spline = select_model(
        DataAvailability(
            technique="sul_tasto",
            instrument="vln",
            dynamic="pp",
            target_quantity="spectral_centroid",
            n_target_observations=12,
            distinct_pitch_count=12,
            pitch_span_semitones=24,
            spline_design_is_identifiable=True,
            missing_covariates=["beta"],
        )
    )
    assert linear.selected_model_id == "regularized_linear_register_trend"
    assert spline.selected_model_id == "penalized_register_spline"


def test_branch_mute_and_harmonic_and_flautando() -> None:
    mute = select_model(
        DataAvailability(
            technique="con_sordino",
            instrument="vln",
            dynamic="mf",
            target_quantity="EWSD_score_acoustic_balanced",
            n_target_observations=0,
            has_spectra_or_ltas=False,
            authorize_numeric_assumption=True,
        )
    )
    harm = select_model(
        DataAvailability(
            technique="artificial_harmonic",
            instrument="vln",
            dynamic="mf",
            target_quantity="EWSD_score_acoustic_balanced",
            n_target_observations=0,
        )
    )
    flaut = select_model(
        DataAvailability(
            technique="flautando",
            instrument="vln",
            dynamic="mf",
            target_quantity="EWSD_score_acoustic_balanced",
            n_target_observations=0,
        )
    )
    assert mute.selected_model_id == "constant_assumption_fallback"
    assert mute.model_family == "mute_transfer_model"
    assert "beta" not in mute.required_covariates
    assert "ordinary_spectrum_or_ltas" in mute.required_covariates
    # Without enriched modal requests → metadata incomplete
    assert harm.selected_model_id == "harmonic_modal_metadata_gate"
    assert harm.fallback_level == "no_numeric_fallback"
    assert harm.complexity_level == "not_applicable"
    assert flaut.model_family == "execution_target_model"
    assert flaut.selected_model_id != "constant_technique_effect_over_smoothed_baseline"


def test_export_audit_fields_filled(tmp_path: Path) -> None:
    rows = _ordinary()
    all_r = []
    for tech in ("con_sordino", "sul_tasto", "sul_ponticello", "artificial_harmonic"):
        kwargs = {"pitches": ["A4", "G3"]} if not tech.endswith("harmonic") else {}
        all_r.extend(
            predict_register(rows, technique=tech, instrument="vln", dynamic="mf", **kwargs)
        )
    out = export_nonlinear_workbook(
        all_r,
        tmp_path / "audit.xlsx",
        run_metadata={"requested_method": "automatic", "method": "hierarchical_spline"},
    )
    xl = pd.ExcelFile(out)
    assert "Model_Selection_Audit" in xl.sheet_names
    assert "Run_Summary" in xl.sheet_names
    run = pd.read_excel(out, sheet_name="Run_Summary")
    keys = set(run["key"].astype(str))
    assert "requested_method" in keys
    assert "baseline_model" in keys
    assert "selected_technique_model.con_sordino" in keys
    req = run.loc[run["key"] == "requested_method", "value"].iloc[0]
    assert str(req) == "automatic"
    # Applied technique models must not be summarized as hierarchical_spline
    tech_rows = run[run["key"].astype(str).str.startswith("selected_technique_model.")]
    assert not tech_rows["value"].astype(str).str.contains("hierarchical_spline").any()

    post = pd.read_excel(out, sheet_name="Posterior_Summary")
    # Numeric rows must have provenance
    numeric = post[post["value_kind"] != "unavailable"]
    assert (numeric["assumptions_used"].astype(str).str.len() > 0).all()
    assert (numeric["baseline_record_ids"].astype(str).str.len() > 0).all()
    assert (numeric["model_family"].astype(str).str.len() > 0).all()
    assert (numeric["selection_reason"].astype(str).str.len() > 0).all()
    assert (numeric["candidate_model_ids"].astype(str).str.len() > 0).all()
    assert (numeric["rejected_model_ids"].astype(str).str.len() > 0).all()

    harm = post[post["technique"] == "artificial_harmonic"]
    assert (harm["shape_source"] == "not_applicable").all()
    assert (harm["model_status"] == "modal_frequencies_generated_acoustic_values_unavailable").all()
    assert "extrapolation_method" in post.columns
    assert "Note_Level_Results" in xl.sheet_names
    # assumptions_used must be ASSUMP_* only
    assert not numeric["assumptions_used"].astype(str).str.contains("selection_reason=").any()
    assert not numeric["assumptions_used"].astype(str).str.contains("effect_kind=").any()
    assert "assumptions_trace" in post.columns
    assert "estimate_mean" in post.columns
    # Bayesian columns empty for frequentist/assumption path
    assert post["posterior_mean"].isna().all() or (post["posterior_mean"].astype(str) == "None").all()


def test_predict_fills_assumptions_and_baseline_ids() -> None:
    r = predict_register(_ordinary(), technique="con_sordino", instrument="vln", dynamic="mf", pitches=["A4"])[0]
    assert r.assumptions_used
    assert all(a.startswith("ASSUMP_") for a in r.assumptions_used)
    assert r.assumption_ids == r.assumptions_used or set(r.assumptions_used) <= set(r.assumption_ids)
    assert r.assumptions_trace  # detailed prose lives here
    assert r.baseline_record_ids
    assert r.model_family == "mute_transfer_model"
    assert "beta" not in (r.missing_covariates or [])
    assert r.estimate_mean is not None
    assert r.posterior_mean is None
    assert r.evidence_tier.value == "LEVEL_1_ASSUMPTION_ONLY"
    assert r.model_selection_status
    assert r.interval_type == "assumption_distribution_interval"
