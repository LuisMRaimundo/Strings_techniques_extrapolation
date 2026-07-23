"""Phase 3b — curated evidence-package ingestion and density activation gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.literature.activation import (
    ApplicabilityQuery,
    db_value_is_not_density,
    evaluate_parameter_activation,
    match_applicability,
)
from string_technique_model.literature.extracts import EvidenceExtract
from string_technique_model.literature.package_ingestion import ingest_evidence_package
from string_technique_model.literature.parameter_ledger import load_parameter_config
from string_technique_model.literature.scales import assert_not_db_density, is_decibel_scale
from string_technique_model.literature.source_registry import LiteratureSource, SourceRegistry


def _verified_registry_and_extract(
    *,
    source_id: str = "SRC_GATE",
    instrument: str = "vln",
    technique: str = "artificial_harmonic",
    mapping: str = "direct_same_metric",
    harmonic_type: str = "artificial",
    mute_type: str | None = None,
) -> tuple[SourceRegistry, dict[str, EvidenceExtract], EvidenceExtract]:
    src = LiteratureSource(
        source_id=source_id,
        source_type="peer_reviewed_journal",
        full_citation="Gate, A. (2020). Title. Journal, 1(1), 1-2.",
        authors=["Gate, A."],
        year=2020,
        title="Title",
        journal_or_publisher="Journal",
        volume="1",
        pages="1-2",
        DOI="10.0/gate",
        local_file_path=str(PACKAGE_ROOT / "configs" / "literature_sources.yaml"),
        evidence_status="verified_local_source",
        instruments_covered=[instrument],
        techniques_covered=[technique],
    )
    ext = EvidenceExtract(
        evidence_id="EV_GATE_001",
        source_id=source_id,
        instrument=instrument,
        technique=technique,
        page_start=1,
        paraphrased_claim="Direct density extract for gate tests",
        quantitative_or_qualitative="quantitative",
        reported_value=1.1,
        original_unit="dimensionless",
        canonical_unit="dimensionless",
        canonical_variable_name="density_value",
        directness="direct_same_instrument_same_technique",
        density_mapping_status=mapping,
        curator_verification_status="validated",
        harmonic_type=harmonic_type,
        mute_type=mute_type,
        numerical_scale="raw_density",
        operation_type="multiplicative_ratio",
        extraction_method="manual_extraction_from_table",
    )
    return SourceRegistry([src]), {ext.evidence_id: ext}, ext


def _base_active_param(**overrides):
    param = {
        "parameter_id": "GATE_DENSITY_OK",
        "instrument": "vln",
        "technique": "artificial_harmonic",
        "operation_type": "multiplicative_ratio",
        "numerical_scale": "raw_density",
        "unit": "dimensionless",
        "reported_value": 1.1,
        "source_ids": ["SRC_GATE"],
        "evidence_ids": ["EV_GATE_001"],
        "density_mapping_status": "direct_same_metric",
        "parameter_status": "directly_extracted",
        "active_for_density_prediction": True,
        "applicable_harmonic_type": "artificial",
        "direct_or_transferred": "direct",
    }
    param.update(overrides)
    return param


def test_1_decibel_level_not_interpreted_as_density():
    assert is_decibel_scale("decibel_power")
    with pytest.raises(ValueError, match="density"):
        assert_not_db_density("decibel_power", context="test")
    param = _base_active_param(
        numerical_scale="decibel_power",
        operation_type="decibel_gain",
        unit="dB",
        density_mapping_status="indirect_proxy",
        active_for_density_prediction=False,
    )
    assert db_value_is_not_density(param)


def test_2_dynamic_range_not_density_ratio():
    cfg = load_parameter_config()
    dr = next(p for p in cfg["parameters"] if p["parameter_id"] == "MEYER_VLN_HARMONIC_DYNAMIC_RANGE")
    assert dr["reported_value"] == 20.0
    assert dr["density_mapping_status"] == "indirect_proxy"
    assert dr["active_for_density_prediction"] is False
    result = ingest_evidence_package(dry_run=True)
    inactive_ids = {p["parameter_id"] for p in result.inactive_parameters}
    assert "MEYER_VLN_HARMONIC_DYNAMIC_RANGE" in inactive_ids
    assert result.active_parameters == []


def test_3_qualitative_cannot_create_numerical_coefficient():
    result = ingest_evidence_package(dry_run=True)
    for m in result.mechanisms:
        if m["mechanism_name"] == "frequency_dependent_spectral_redistribution":
            assert m["status"] in {"supported", "partially_supported"}
    assert not any(
        p.get("reported_value") == 1.25 and p.get("active_for_density_prediction")
        for p in result.candidate_parameters
    )


def test_4_supported_mechanism_without_active_parameter():
    result = ingest_evidence_package(dry_run=True)
    sp_mechs = [
        m
        for m in result.mechanisms
        if m["technique"] == "sul_ponticello"
        and m["mechanism_name"] == "frequency_dependent_spectral_redistribution"
    ]
    assert sp_mechs
    assert any(m.get("supported") in {True, "true", "partially_supported"} or "support" in str(m.get("status")) for m in sp_mechs)
    assert result.active_parameters == []
    prohibited = next(
        p for p in result.candidate_parameters if p["parameter_id"] == "PROHIBITED_SUL_PONT_DENSITY_RATIO_1_25"
    )
    assert prohibited["parameter_status"] == "prohibited"


def test_5_missing_applicability_prevents_universal_application():
    reg, by_id, _ = _verified_registry_and_extract()
    param = _base_active_param()
    # Remove applicability metadata
    param.pop("applicable_harmonic_type")
    decision = evaluate_parameter_activation(param, registry=reg, extracts_by_id=by_id, target=None)
    assert decision.active is False
    assert "missing_applicability" in decision.reasons
    assert decision.applicability_status == "insufficiently_specified"


def test_6_7_8_violin_not_applied_to_other_instruments():
    reg, by_id, _ = _verified_registry_and_extract()
    param = _base_active_param(instrument="vln")
    for other in ("vla", "vlc", "cb"):
        decision = evaluate_parameter_activation(
            param,
            registry=reg,
            extracts_by_id=by_id,
            target=ApplicabilityQuery(
                instrument=other,
                technique="artificial_harmonic",
                harmonic_type="artificial",
            ),
        )
        assert decision.active is False
        assert "instrument_mismatch" in decision.reasons


def test_9_natural_harmonic_does_not_activate_artificial():
    reg, by_id, _ = _verified_registry_and_extract()
    param = _base_active_param(applicable_harmonic_type="artificial")
    decision = evaluate_parameter_activation(
        param,
        registry=reg,
        extracts_by_id=by_id,
        target=ApplicabilityQuery(
            instrument="vln",
            technique="artificial_harmonic",
            harmonic_type="natural",
        ),
    )
    assert decision.active is False
    assert "harmonic_type_mismatch" in decision.reasons


def test_10_11_mute_type_respected_heavy_vs_orchestral():
    result = ingest_evidence_package(dry_run=True)
    orch = next(p for p in result.candidate_parameters if p["parameter_id"] == "MEYER_VLN_MUTE_GLOBAL_REDUCTION")
    heavy = next(p for p in result.candidate_parameters if p["parameter_id"] == "MEYER_VLN_MUTE_HEAVY_REDUCTION")
    assert orch["applicable_mute_type"] == "orchestral"
    assert heavy["applicable_mute_type"] == "heavy_practice"
    assert orch["reported_value"] != heavy["reported_value"]

    ok, status = match_applicability(
        orch,
        ApplicabilityQuery(instrument="vln", technique="con_sordino", mute_type="heavy_practice"),
    )
    assert ok is False
    assert status == "mute_type_mismatch"


def test_12_source_verification_required():
    """Verified Meyer is no longer blocked for source_not_verified; pending sources still are."""
    result = ingest_evidence_package(dry_run=True)
    meyer_decisions = [d for d in result.decisions if d.parameter_id.startswith("MEYER_")]
    assert meyer_decisions
    for d in meyer_decisions:
        assert "source_not_verified" not in d.reasons

    pending_src = LiteratureSource(
        source_id="SRC_PENDING_GATE",
        source_type="peer_reviewed_journal",
        full_citation="Pending, A. (2020). Title. Journal, 1(1), 1-2.",
        authors=["Pending, A."],
        year=2020,
        title="Title",
        journal_or_publisher="Journal",
        volume="1",
        pages="1-2",
        DOI="10.0/pending-gate",
        local_file_path=None,
        evidence_status="pending_local_source",
        instruments_covered=["vln"],
        techniques_covered=["artificial_harmonic"],
    )
    reg = SourceRegistry([pending_src])
    _, by_id, ext = _verified_registry_and_extract(source_id="SRC_PENDING_GATE")
    # Force extract source_id match; registry remains pending (no verified file).
    param = {
        "parameter_id": "P_PENDING",
        "instrument": "vln",
        "technique": "artificial_harmonic",
        "parameter_status": "directly_extracted",
        "operation_type": "multiplicative_ratio",
        "numerical_scale": "density_ratio",
        "unit": "dimensionless_ratio",
        "reported_value": 1.1,
        "source_ids": ["SRC_PENDING_GATE"],
        "evidence_ids": [ext.evidence_id],
        "density_mapping_type": "direct_same_metric",
        "active_for_density_prediction": False,
    }
    decision = evaluate_parameter_activation(param, registry=reg, extracts_by_id=by_id)
    assert decision.active is False
    assert "source_not_verified" in decision.reasons


def test_13_evidence_verification_required_for_activation():
    reg = SourceRegistry(
        [
            LiteratureSource(
                source_id="SRC_GATE",
                source_type="peer_reviewed_journal",
                full_citation="Gate, A. (2020). Title. Journal, 1(1), 1-2.",
                authors=["Gate, A."],
                year=2020,
                title="Title",
                journal_or_publisher="Journal",
                volume="1",
                pages="1-2",
                DOI="10.0/gate2",
                local_file_path=str(PACKAGE_ROOT / "configs" / "literature_sources.yaml"),
                evidence_status="verified_local_source",
            )
        ]
    )
    unverified = EvidenceExtract(
        evidence_id="EV_UNVER",
        source_id="SRC_GATE",
        instrument="vln",
        technique="artificial_harmonic",
        page_start=1,
        paraphrased_claim="x",
        quantitative_or_qualitative="quantitative",
        reported_value=1.0,
        original_unit="dimensionless",
        directness="direct_same_instrument_same_technique",
        density_mapping_status="direct_same_metric",
        curator_verification_status="unverified",
    )
    param = _base_active_param(evidence_ids=["EV_UNVER"])
    decision = evaluate_parameter_activation(
        param,
        registry=reg,
        extracts_by_id={"EV_UNVER": unverified},
        target=ApplicabilityQuery(
            instrument="vln", technique="artificial_harmonic", harmonic_type="artificial"
        ),
    )
    assert decision.active is False
    assert "evidence_not_verified" in decision.reasons


def test_14_density_mapping_required():
    reg, by_id, _ = _verified_registry_and_extract()
    param = _base_active_param(density_mapping_status=None)
    decision = evaluate_parameter_activation(
        param,
        registry=reg,
        extracts_by_id=by_id,
        target=ApplicabilityQuery(
            instrument="vln", technique="artificial_harmonic", harmonic_type="artificial"
        ),
    )
    assert decision.active is False
    assert "missing_density_mapping" in decision.reasons


def test_15_active_parameters_have_complete_provenance():
    # Construct a fully qualifying parameter; should activate.
    reg, by_id, _ = _verified_registry_and_extract()
    param = _base_active_param()
    decision = evaluate_parameter_activation(
        param,
        registry=reg,
        extracts_by_id=by_id,
        target=ApplicabilityQuery(
            instrument="vln",
            technique="artificial_harmonic",
            harmonic_type="artificial",
        ),
    )
    assert decision.active is True
    assert decision.reasons == []
    assert param["source_ids"] and param["evidence_ids"]
    assert param["operation_type"] and param["numerical_scale"] and param["unit"]


def test_16_inactive_parameters_retain_explicit_failure_reasons():
    result = ingest_evidence_package(dry_run=True)
    assert result.inactive_parameters
    for row in result.activation_failures:
        assert row["failure_reasons"]
        assert row["active"] is False


def test_17_exactly_sixteen_evidence_cells_rebuilt():
    result = ingest_evidence_package(dry_run=True)
    assert len(result.rebuilt_matrix) == 16


def test_18_no_technique_density_prediction_generated():
    result = ingest_evidence_package(dry_run=True)
    assert result.density_prediction_produced is False
    for row in result.rebuilt_matrix:
        assert "estimated_density" not in row
        assert "predicted_density" not in row
        assert "density_multiplier" not in row


def test_package_outputs_written(tmp_path: Path):
    out = tmp_path / "literature"
    reports = tmp_path / "reports"
    result = ingest_evidence_package(output_dir=out, reports_dir=reports, dry_run=False)
    for name in (
        "evidence_extracts.csv",
        "instrument_technique_evidence_matrix.csv",
        "parameter_evidence_ledger.csv",
        "density_mapping_matrix.csv",
        "unsupported_parameters.csv",
        "validated_sources.csv",
        "validated_evidence_extracts.csv",
        "validated_parameters.csv",
        "active_parameters.csv",
        "inactive_parameters.csv",
        "parameter_activation_failures.csv",
        "rebuilt_evidence_matrix.csv",
    ):
        assert (out / name).exists(), name
    assert (reports / "literature_parameter_validation.md").exists()
    assert result.summary["n_active_parameters"] == 0


def test_provisional_grade_profile_approximately_matches_curation():
    result = ingest_evidence_package(dry_run=True)
    grades = {f"{r['instrument']}/{r['technique']}": r["evidence_grade"] for r in result.rebuilt_matrix}
    assert grades["vln/artificial_harmonic"] in {"B", "C"}
    assert grades["vla/artificial_harmonic"] in {"C", "B"}
    assert grades["vlc/artificial_harmonic"] in {"B", "C"}
    assert grades["cb/artificial_harmonic"] in {"B", "C"}
    assert grades["vln/sul_ponticello"] in {"B", "C", "D"}
    assert grades["vln/sul_tasto"] in {"C", "D"}
    assert grades["vln/con_sordino"] in {"B", "C"}
    assert grades["vla/con_sordino"] in {"B", "C"}
