"""User assumption registry + ordinary→technique workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from string_technique_model.assumptions import (
    assumption_label_fields,
    clear_assumption_registry_cache,
    load_user_assumption_registry,
    resolve_user_assumptions,
)
from string_technique_model.assumptions.models import UserAssumption
from string_technique_model.prediction.from_ordinary import (
    ordinary_cdm_to_baseline_long,
    predict_from_ordinary,
)
from string_technique_model.prediction.pipeline import build_predictions


def _write_assumption_registry(path: Path, assumptions: list[dict]) -> None:
    payload = {
        "version": "test",
        "schema_version": "user_assumption_v1",
        "registry_kind": "user_numerical_assumptions",
        "literature_validated": False,
        "default_active_for_density_prediction": False,
        "assumptions": assumptions,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    clear_assumption_registry_cache()


def _valid_assumption(**overrides):
    base = {
        "assumption_id": "UA_TEST_VLN_SP_RATIO",
        "name": "test_ratio",
        "instrument": "vln",
        "technique": "sul_ponticello",
        "operation_type": "multiplicative_ratio",
        "reported_value": 1.1,
        "unit": "dimensionless_ratio",
        "numerical_scale": "density_ratio",
        "compatible_links": ["log", "identity"],
        "source_space": "density",
        "target_space": "density",
        "uncertainty_sd": 0.05,
        "applicable_dynamic": "mf",
        "applicable_metric_definition_id": "ewsd_v1",
        "scope_note": "unit test only",
        "operationalisation": "Synthetic test assumption for unit tests only.",
        "provenance": "test fixture; not literature",
        "active_for_density_prediction": False,
        "curator_status": "draft",
        "literature_validated": False,
    }
    base.update(overrides)
    return base


def test_registry_loads_empty_by_default():
    reg = load_user_assumption_registry()
    assert reg.literature_validated is False
    assert reg.default_active_for_density_prediction is False


def test_assumption_cannot_claim_literature_validated():
    with pytest.raises(ValidationError):
        UserAssumption.model_validate(_valid_assumption(literature_validated=True))


def test_assumptions_inactive_unless_run_and_flag_enabled(tmp_path: Path):
    reg_path = tmp_path / "ua.yaml"
    _write_assumption_registry(
        reg_path,
        [_valid_assumption(active_for_density_prediction=True)],
    )
    ctx = {
        "instrument": "vln",
        "technique": "sul_ponticello",
        "dynamic": "mf",
        "target_metric_definition_id": "ewsd_v1",
    }
    inactive = resolve_user_assumptions(
        context=ctx, link="log", activation_enabled=False, path=str(reg_path)
    )
    assert inactive and inactive[0].status == "inactive"
    assert "user_assumption_activation_disabled_for_run" in inactive[0].reasons

    active = resolve_user_assumptions(
        context=ctx, link="log", activation_enabled=True, path=str(reg_path)
    )
    assert active[0].status == "active"


def test_assumption_label_never_literature():
    fields = assumption_label_fields(["UA_X"])
    assert fields["result_basis"] == "user_assumption"
    assert fields["literature_validated"] is False
    assert fields["evidence_based"] is False
    assert "not literature-validated" in fields["provenance"].lower()
    assert "UA_X" in fields["assumption_ids_used"]


def test_from_ordinary_default_is_na_plus_qualitative(tmp_path: Path):
    result = predict_from_ordinary(
        instrument="vln",
        dynamic="mf",
        techniques=["sul_ponticello", "sul_tasto"],
        output_dir=tmp_path / "fo",
        activate_user_assumptions=False,
        n_draws=50,
        random_seed=1,
    )
    assert result.activation_mode == "evidence_and_qualitative_only"
    assert result.prediction.rows
    assert all(r.get("estimated_density_mean") is None for r in result.prediction.rows)
    assert all(r.get("literature_validated") in {False, None} for r in result.prediction.rows)
    assert any(r.get("tendency") for r in result.qualitative_rows)
    assert (tmp_path / "fo" / "ordinary_to_technique_summary.csv").exists()
    assert (tmp_path / "fo" / "README_RESULT_BASIS.md").exists()


def test_from_ordinary_with_activated_assumption_is_labelled(tmp_path: Path, monkeypatch):
    reg_path = tmp_path / "ua.yaml"
    _write_assumption_registry(
        reg_path,
        [_valid_assumption(active_for_density_prediction=True, reported_value=1.2)],
    )
    from string_technique_model.prediction import pipeline as pipe

    original_load = pipe.load_prediction_config

    def _cfg():
        cfg = original_load()
        cfg = dict(cfg)
        ua = dict(cfg.get("user_assumptions") or {})
        ua["registry_path"] = str(reg_path)
        ua["activation_enabled"] = False
        cfg["user_assumptions"] = ua
        return cfg

    monkeypatch.setattr(pipe, "load_prediction_config", _cfg)

    baseline = ordinary_cdm_to_baseline_long(instrument="vln", dynamic="mf")
    # Keep a tiny pitch slice for speed
    baseline = baseline.head(3)
    bl = tmp_path / "bl.csv"
    baseline.to_csv(bl, index=False)

    result = build_predictions(
        baseline_path=bl,
        instruments=["vln"],
        techniques=["sul_ponticello"],
        output_dir=tmp_path / "pred",
        n_draws=40,
        random_seed=2,
        dynamic=["mf"],
        activate_user_assumptions=True,
    )
    numerical = [r for r in result.rows if r.get("estimated_density_mean") is not None]
    assert numerical
    for r in numerical:
        assert r["result_basis"] == "user_assumption"
        assert r["literature_validated"] is False
        assert r["evidence_based"] is False
        assert r["prediction_status"] == "predicted_from_user_assumption"
        assert "UA_TEST_VLN_SP_RATIO" in str(r["assumption_ids_used"])
        assert "not literature-validated" in str(r["provenance"]).lower()
        # Must not copy ordinary unchanged under a 1.2 ratio
        assert r["estimated_density_mean"] != r["baseline_density"]


def test_ordinary_cdm_flatten_mf_only():
    frame = ordinary_cdm_to_baseline_long(instrument="violin", dynamic="mf")
    assert not frame.empty
    assert set(frame["dynamic"].unique()) == {"mf"}
    assert set(frame["instrument"].unique()) == {"vln"}
    assert set(frame["technique"].unique()) == {"ordinary"}
