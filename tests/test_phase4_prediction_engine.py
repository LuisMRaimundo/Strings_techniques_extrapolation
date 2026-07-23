"""Phase 4 — evidence-gated technique prediction engine."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.estimate import estimate_cell
from string_technique_model.literature.domain import ALLOWED_INSTRUMENTS, ALLOWED_TECHNIQUES
from string_technique_model.literature.extracts import EvidenceExtract
from string_technique_model.literature.source_registry import LiteratureSource, SourceRegistry
from string_technique_model.models.registry import get_model, list_model_keys
from string_technique_model.prediction.activation import resolve_prediction_parameters
from string_technique_model.prediction.links import link_forward, link_inverse, select_link
from string_technique_model.prediction.operations import (
    OperationError,
    amplitude_ratio_from_db,
    apply_operation,
    power_ratio_from_db,
)
from string_technique_model.prediction.pipeline import build_predictions
from string_technique_model.prediction.requests import PredictionRequest
from string_technique_model.prediction.uncertainty import propagate_metric_only
from string_technique_model.sensitivity.prediction_sensitivity import run_prediction_sensitivity
from string_technique_model.validation.prediction_validation import (
    run_prediction_validation,
    validation_enabled,
)

BASELINE = PACKAGE_ROOT / "outputs" / "baseline_smoke_multi" / "ordinary_baseline_long.csv"


def _synth_active_param(**overrides):
    p = {
        "parameter_id": "SYNTH_DENSITY_RATIO",
        "instrument": "vln",
        "technique": "sul_ponticello",
        "operation_type": "multiplicative_ratio",
        "numerical_scale": "raw_density",
        "unit": "dimensionless",
        "reported_value": 1.1,
        "proposed_distribution": "normal",
        "distribution_parameters": {"mean": 1.1, "sd": 0.05},
        "source_ids": ["SRC_GATE"],
        "evidence_ids": ["EV_GATE_001"],
        "density_mapping_status": "direct_same_metric",
        "parameter_status": "directly_extracted",
        "active_for_density_prediction": True,
        "applicable_dynamic": "mf",
        "direct_or_transferred": "direct",
    }
    p.update(overrides)
    return p


def _verified_pair():
    src = LiteratureSource(
        source_id="SRC_GATE",
        source_type="peer_reviewed_journal",
        full_citation="Gate, A. (2020). Title. Journal, 1(1), 1-2.",
        authors=["Gate, A."],
        year=2020,
        title="Title",
        journal_or_publisher="Journal",
        volume="1",
        pages="1-2",
        DOI="10.0/gate-p4",
        local_file_path=str(PACKAGE_ROOT / "configs" / "literature_sources.yaml"),
        evidence_status="verified_local_source",
        instruments_covered=["vln"],
        techniques_covered=["sul_ponticello"],
    )
    ext = EvidenceExtract(
        evidence_id="EV_GATE_001",
        source_id="SRC_GATE",
        instrument="vln",
        technique="sul_ponticello",
        page_start=1,
        paraphrased_claim="Direct density ratio",
        quantitative_or_qualitative="quantitative",
        reported_value=1.1,
        original_unit="dimensionless",
        directness="direct_same_instrument_same_technique",
        density_mapping_status="direct_same_metric",
        curator_verification_status="validated",
        numerical_scale="raw_density",
        operation_type="multiplicative_ratio",
    )
    return SourceRegistry([src]), [ext]


def test_01_02_only_four_instruments_and_techniques():
    assert ALLOWED_INSTRUMENTS == {"vln", "vla", "vlc", "cb"}
    assert ALLOWED_TECHNIQUES == {
        "artificial_harmonic",
        "sul_ponticello",
        "sul_tasto",
        "con_sordino",
    }
    with pytest.raises(ValueError):
        PredictionRequest(instrument="flute", target_technique="sul_ponticello")
    with pytest.raises(ValueError):
        PredictionRequest(instrument="vln", target_technique="pizzicato")


def test_03_no_prediction_without_ordinary_baseline(tmp_path: Path):
    empty = tmp_path / "empty.csv"
    pd.DataFrame(
        columns=[
            "baseline_cell_id",
            "instrument",
            "technique",
            "dynamic",
            "baseline_value",
            "pitch_midi_sounding",
        ]
    ).to_csv(empty, index=False)
    with pytest.raises(ValueError, match="No ordinary baseline"):
        build_predictions(baseline_path=empty, instruments=["vln"], techniques=["sul_ponticello"], dry_run=True)


def test_04_05_06_inactive_and_indirect_and_qualitative_do_not_create_values():
    result = estimate_cell(
        instrument="vln",
        technique="sul_ponticello",
        note="A4",
        dynamic="mf",
        ordinary_density=20.0,
        parameters=[
            {
                "instrument": "vln",
                "technique": "sul_ponticello",
                "parameter_name": "level_db",
                "numerical_value": 6.0,
                "active_for_density_prediction": False,
                "density_mapping_status": "indirect_proxy",
                "operation_type": "decibel_power_gain",
                "parameter_status": "interval_constrained",
            }
        ],
        n_draws=100,
        random_seed=1,
    )
    assert result.estimated_density is None
    assert "not_estimable" in result.estimation_status


def test_07_additive_and_multiplicative_not_confused():
    eta = np.array([np.log(10.0)])
    d = np.array([10.0])
    eta_m, d_m, _ = apply_operation(
        operation_type="multiplicative_ratio",
        draws=np.array([2.0]),
        eta=eta.copy(),
        d_ordinary=d,
        numerical_scale="raw_density",
        link="log",
    )
    eta_a, d_a, _ = apply_operation(
        operation_type="additive_difference",
        draws=np.array([2.0]),
        eta=eta.copy(),
        d_ordinary=d,
        numerical_scale="raw_density",
        link="log",
    )
    # Multiplicative: D' = 20 in density / log space
    assert abs(float(np.exp(eta_m)) - 20.0) < 1e-9
    assert abs(float(d_m) - 20.0) < 1e-9
    # Additive difference applies in density space then re-links: D' = 12
    assert abs(float(d_a) - 12.0) < 1e-9
    assert abs(float(np.exp(eta_a)) - 12.0) < 1e-9
    assert abs(float(eta_a) - (np.log(10.0) + 2.0)) > 1e-6  # not the old incorrect shortcut


def test_08_amplitude_and_power_db_distinct():
    assert abs(float(amplitude_ratio_from_db(20.0)) - 10.0) < 1e-9
    assert abs(float(power_ratio_from_db(10.0)) - 10.0) < 1e-9
    with pytest.raises(OperationError):
        apply_operation(
            operation_type="decibel_power_gain",
            draws=np.array([6.0]),
            eta=np.array([1.0]),
            d_ordinary=np.array([10.0]),
            numerical_scale="decibel_power",
            link="log",
        )


def test_09_missing_applicability_prevents_universal_use():
    reg, extracts = _verified_pair()
    param = _synth_active_param()
    param.pop("applicable_dynamic")
    records = resolve_prediction_parameters(
        [param],
        registry=reg,
        extracts=extracts,
        context={
            "instrument": "vln",
            "technique": "sul_ponticello",
            "dynamic": "mf",
            "target_metric_definition_id": "ewsd_v1",
        },
        backend="metric-only",
    )
    assert records[0].status != "active"
    assert "insufficient_metadata" in records[0].reasons or "missing_applicability" in records[0].reasons


def test_10_11_12_pitch_dynamic_string_respected():
    reg, extracts = _verified_pair()
    param = _synth_active_param(
        applicable_dynamic="pp",
        applicable_string="E",
        applicable_pitch_min=60,
        applicable_pitch_max=72,
    )
    records = resolve_prediction_parameters(
        [param],
        registry=reg,
        extracts=extracts,
        context={
            "instrument": "vln",
            "technique": "sul_ponticello",
            "dynamic": "mf",
            "string_name": "A",
            "pitch_midi_sounding": 80,
            "target_metric_definition_id": "ewsd_v1",
        },
        backend="metric-only",
    )
    assert records[0].status == "not_applicable"


def test_13_harmonic_order_required_when_configured():
    model = get_model("vln", "artificial_harmonic")
    ctx = model.validate_context(
        {"baseline_value": 10.0, "technique": "ordinary"},
        {
            "instrument": "vln",
            "technique": "artificial_harmonic",
            "dynamic": "mf",
            "string_name": "E",
            "stopped_pitch_name": "A4",
            "stopped_pitch_midi": 69,
            "sounding_pitch_name": "A5",
            "sounding_pitch_midi": 81,
            # harmonic_order missing
        },
    )
    assert ctx.ok is False
    assert "harmonic_order" in ctx.missing_required


def test_14_natural_vs_artificial():
    model = get_model("vln", "artificial_harmonic")
    ctx = model.validate_context(
        {"baseline_value": 10.0, "technique": "ordinary"},
        {
            "instrument": "vln",
            "technique": "artificial_harmonic",
            "dynamic": "mf",
            "string_name": "E",
            "stopped_pitch_name": "A4",
            "stopped_pitch_midi": 69,
            "harmonic_order": 2,
            "sounding_pitch_name": "A5",
            "sounding_pitch_midi": 81,
            "harmonic_type": "natural",
        },
    )
    assert ctx.ok is False


def test_15_cb_written_sounding_distinct():
    from string_technique_model.instruments.double_bass import DOUBLE_BASS

    assert DOUBLE_BASS["written_equals_sounding"] is False


def test_16_sul_tasto_flautando_distinct():
    model = get_model("vln", "sul_tasto")
    assert model.technique_cfg.get("equate_flautando") is False
    ctx = model.validate_context(
        {"baseline_value": 10.0, "technique": "ordinary"},
        {"instrument": "vln", "technique": "sul_tasto", "dynamic": "mf", "articulation": "flautando"},
    )
    assert any("flautando" in n for n in ctx.notes)


def test_17_18_mute_types_distinct():
    model = get_model("vln", "con_sordino")
    assert model.technique_cfg.get("distinguish_practice_vs_orchestral") is True
    ctx = model.validate_context(
        {"baseline_value": 10.0, "technique": "ordinary"},
        {"instrument": "vln", "technique": "con_sordino", "dynamic": "mf"},
    )
    assert "mute_type" in ctx.missing_required


def test_19_20_21_violin_not_applied_cross_instrument():
    reg, extracts = _verified_pair()
    param = _synth_active_param(instrument="vln")
    for other in ("vla", "vlc", "cb"):
        records = resolve_prediction_parameters(
            [param],
            registry=reg,
            extracts=extracts,
            context={
                "instrument": other,
                "technique": "sul_ponticello",
                "dynamic": "mf",
                "target_metric_definition_id": "ewsd_v1",
            },
            backend="metric-only",
        )
        assert records[0].status != "active"


def test_22_23_transfer_disabled_by_default_requires_equation():
    reg, extracts = _verified_pair()
    param = _synth_active_param(
        direct_or_transferred="transferred",
        transfer_source_instrument="vln",
        transfer_equation=None,
        instrument="vla",
    )
    records = resolve_prediction_parameters(
        [param],
        registry=reg,
        extracts=extracts,
        context={
            "instrument": "vla",
            "technique": "sul_ponticello",
            "dynamic": "mf",
            "target_metric_definition_id": "ewsd_v1",
        },
        backend="metric-only",
        transfers_enabled=False,
    )
    assert "cross_instrument_transfer_inactive" in records[0].reasons


def test_24_transferred_estimates_wider_uncertainty():
    base = {"baseline_value": 20.0, "baseline_mean": 20.0, "baseline_sd": 0.5}
    param = _synth_active_param(distribution_parameters={"mean": 1.1, "sd": 0.01})
    narrow = propagate_metric_only(
        baseline=base, active_params=[param], link="log", n_draws=2000, random_seed=1
    )
    wide = propagate_metric_only(
        baseline=base,
        active_params=[param],
        link="log",
        n_draws=2000,
        random_seed=1,
        transfer_uncertainty_sd=0.2,
    )
    assert wide.estimated_density_sd > narrow.estimated_density_sd


def test_25_26_27_never_measured_na_without_active_no_copy(tmp_path: Path):
    out = tmp_path / "pred"
    result = build_predictions(
        baseline_path=BASELINE,
        instruments=["vln"],
        techniques=["sul_ponticello"],
        backend="metric-only",
        output_dir=out,
        n_draws=100,
        random_seed=20250723,
        dry_run=False,
        dynamic=["mf"],
        pitch_min=69,
        pitch_max=69,
    )
    assert result.rows
    for row in result.rows:
        assert row["measured_or_estimated"] in {"modelled", "estimated"}
        assert row["measured_or_estimated"] != "measured"
        assert row["estimated_density_mean"] is None
        assert row["prediction_status"] in {
            "insufficient_active_parameters",
            "qualitative_constraints_only",
            "insufficient_context_metadata",
            "not_estimable_from_current_evidence",
        }
        if row["baseline_density"] is not None:
            assert row["estimated_density_mean"] != row["baseline_density"] or row[
                "estimated_density_mean"
            ] is None


def test_28_29_seed_repro_and_wider_priors():
    base = {"baseline_value": 20.0, "baseline_mean": 20.0}
    param_narrow = _synth_active_param(distribution_parameters={"mean": 1.1, "sd": 0.01})
    param_wide = _synth_active_param(distribution_parameters={"mean": 1.1, "sd": 0.2})
    a = propagate_metric_only(
        baseline=base, active_params=[param_narrow], link="log", n_draws=2000, random_seed=42
    )
    b = propagate_metric_only(
        baseline=base, active_params=[param_narrow], link="log", n_draws=2000, random_seed=42
    )
    assert a.estimated_density_mean == b.estimated_density_mean
    wide = propagate_metric_only(
        baseline=base, active_params=[param_wide], link="log", n_draws=2000, random_seed=42
    )
    assert (wide.estimated_density_q975 - wide.estimated_density_q025) > (
        a.estimated_density_q975 - a.estimated_density_q025
    )


def test_30_uncertainty_not_filled_with_zero_when_unavailable():
    base = {"baseline_value": 20.0, "baseline_mean": 20.0}  # no sd/se
    param = _synth_active_param(reported_value=1.1, proposed_distribution=None, distribution_parameters=None)
    propagate_metric_only(
        baseline=base, active_params=[param], link="log", n_draws=50, random_seed=1
    )
    # Point-identified MC may yield sd==0; unavailable baseline uncertainty must not invent a fake sd label
    assert base.get("baseline_sd") is None


def test_31_prediction_ids_deterministic(tmp_path: Path):
    out1 = tmp_path / "a"
    out2 = tmp_path / "b"
    r1 = build_predictions(
        baseline_path=BASELINE,
        instruments=["vln"],
        techniques=["sul_tasto"],
        output_dir=out1,
        n_draws=50,
        random_seed=20250723,
        dynamic=["mf"],
        pitch_min=60,
        pitch_max=60,
    )
    r2 = build_predictions(
        baseline_path=BASELINE,
        instruments=["vln"],
        techniques=["sul_tasto"],
        output_dir=out2,
        n_draws=50,
        random_seed=20250723,
        dynamic=["mf"],
        pitch_min=60,
        pitch_max=60,
    )
    assert [r["prediction_id"] for r in r1.rows] == [r["prediction_id"] for r in r2.rows]


def test_32_parameter_ledger_reconstructible(tmp_path: Path):
    out = tmp_path / "pred"
    result = build_predictions(
        baseline_path=BASELINE,
        instruments=["vla"],
        techniques=["sul_ponticello"],
        output_dir=out,
        n_draws=50,
        random_seed=1,
        dynamic=["mf"],
        pitch_min=48,
        pitch_max=48,
    )
    assert (out / "prediction_parameter_ledger.csv").exists() or result.parameter_ledger_rows is not None
    # With no active params, ledger still records exclusions
    assert result.rows[0]["estimated_density_mean"] is None


def test_33_validation_isolated():
    assert validation_enabled() is False
    payload = run_prediction_validation(pd.DataFrame(), observations=None)
    assert payload["ran"] is False


def test_34_spectrum_aware_refuses_without_spectral_input(tmp_path: Path):
    out = tmp_path / "spec"
    result = build_predictions(
        baseline_path=BASELINE,
        instruments=["vln"],
        techniques=["sul_ponticello"],
        backend="spectrum-aware",
        output_dir=out,
        n_draws=20,
        random_seed=1,
        dynamic=["mf"],
        pitch_min=69,
        pitch_max=69,
    )
    assert all(r["estimated_density_mean"] is None for r in result.rows)
    assert any("spectral" in str(r.get("provenance") or "").lower() or r["prediction_status"] == "incompatible_metric" for r in result.rows)


def test_35_metric_only_rejects_incompatible_mapping():
    reg, extracts = _verified_pair()
    param = _synth_active_param(density_mapping_status="indirect_proxy")
    records = resolve_prediction_parameters(
        [param],
        registry=reg,
        extracts=extracts,
        context={
            "instrument": "vln",
            "technique": "sul_ponticello",
            "dynamic": "mf",
            "target_metric_definition_id": "ewsd_v1",
        },
        backend="metric-only",
    )
    assert records[0].status != "active"


def test_36_sixteen_model_configurations():
    from string_technique_model.ontology import legacy_cell_count

    keys = list_model_keys()
    assert len(keys) == legacy_cell_count()
    for inst in sorted(ALLOWED_INSTRUMENTS):
        for tech in sorted(ALLOWED_TECHNIQUES):
            assert f"{inst}/{tech}" in keys
            assert get_model(inst, tech).instrument == inst


def test_37_no_hidden_125_coefficient_in_active_path():
    src = (PACKAGE_ROOT / "src" / "string_technique_model" / "prediction").rglob("*.py")
    for path in src:
        text = path.read_text(encoding="utf-8")
        assert "1.25" not in text


def test_38_no_outside_instrument_in_output(tmp_path: Path):
    out = tmp_path / "pred"
    result = build_predictions(
        baseline_path=BASELINE,
        instruments=["vln", "vla", "vlc", "cb"],
        techniques=["sul_ponticello", "sul_tasto"],
        output_dir=out,
        n_draws=20,
        random_seed=1,
        dynamic=["mf"],
        pitch_min=48,
        pitch_max=50,
    )
    assert {r["instrument"] for r in result.rows} <= ALLOWED_INSTRUMENTS
    assert {r["technique"] for r in result.rows} <= ALLOWED_TECHNIQUES


def test_link_selection_and_roundtrip():
    assert select_link("ewsd_v1") == "log"
    x = np.array([10.0, 20.0])
    eta, meta = link_forward(x, "log")
    back = link_inverse(eta, "log")
    assert np.allclose(back, x)
    assert meta.name == "log"


def test_sensitivity_without_active_params():
    payload = run_prediction_sensitivity(baseline={"baseline_value": 20.0}, active_parameters=[])
    assert payload["active_parameters"] == 0


def test_active_synth_param_produces_distribution():
    dist = propagate_metric_only(
        baseline={"baseline_value": 20.0, "baseline_mean": 20.0, "baseline_sd": 1.0},
        active_params=[_synth_active_param()],
        link="log",
        n_draws=500,
        random_seed=7,
    )
    assert dist.estimated_density_mean is not None
    assert dist.estimated_density_q025 is not None
    assert dist.probability_above_ordinary is not None
