"""Relational scientific provenance resolution (Meyer dynamic-range case)."""

from __future__ import annotations

import pytest

from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.estimate import estimate_cell
from string_technique_model.literature.extracts import EvidenceExtract, load_extracts
from string_technique_model.literature.package_ingestion import ingest_evidence_package
from string_technique_model.literature.parameter_ledger import load_parameter_config
from string_technique_model.literature.source_registry import LiteratureSource, SourceRegistry
from string_technique_model.provenance import (
    ProvenanceError,
    meyer_dynamic_range_is_not_density,
    normalize_source_ids,
    provenance_allows_density_activation,
    resolve_parameter_provenance,
    validate_all_parameters,
    validate_parameter_provenance,
)


def _meyer_param() -> dict:
    cfg = load_parameter_config()
    return next(p for p in cfg["parameters"] if p["parameter_id"] == "MEYER_VLN_HARMONIC_DYNAMIC_RANGE")


def test_01_resolves_citation_through_source_ids():
    registry = SourceRegistry.from_yaml()
    extracts = load_extracts()
    resolved = resolve_parameter_provenance(_meyer_param(), registry, extracts)
    assert "MEYER_ACOUSTICS" in resolved.source_ids
    assert resolved.full_citations
    assert all(c.strip() for c in resolved.full_citations)


def test_02_resolves_extraction_method_through_evidence_ids():
    registry = SourceRegistry.from_yaml()
    extracts = load_extracts()
    resolved = resolve_parameter_provenance(_meyer_param(), registry, extracts)
    assert "EV_MEYER_VLN_HARMONIC_DYNAMIC_RANGE" in resolved.evidence_ids
    assert resolved.extraction_methods
    assert "curator_package" in resolved.extraction_methods


def test_03_no_duplicated_citation_required_on_parameter():
    param = _meyer_param()
    assert "full_citation" not in param or not param.get("full_citation")
    assert "extraction_method" not in param or not param.get("extraction_method")
    assert "source_id" not in param or param.get("source_ids")
    resolved = validate_parameter_provenance(param)
    assert resolved.ok is True


def test_04_missing_source_id_rejected():
    param = dict(_meyer_param())
    param["source_ids"] = []
    param.pop("source_id", None)
    resolved = resolve_parameter_provenance(
        param, SourceRegistry.from_yaml(), load_extracts()
    )
    assert resolved.ok is False
    assert "missing_source_id" in resolved.reasons


def test_05_missing_evidence_id_rejected():
    param = dict(_meyer_param())
    param["evidence_ids"] = []
    param.pop("evidence_id", None)
    resolved = resolve_parameter_provenance(
        param, SourceRegistry.from_yaml(), load_extracts()
    )
    assert resolved.ok is False
    assert "missing_evidence_id" in resolved.reasons


def test_06_incomplete_source_cannot_activate():
    src = LiteratureSource(
        source_id="SRC_INCOMPLETE",
        source_type="book",
        full_citation="Incomplete, A. Title only.",
        authors=["Incomplete, A."],
        title="Title only",
        year=None,
        journal_or_publisher=None,
        evidence_status="incomplete_reference",
        local_file_path=None,
    )
    ext = EvidenceExtract(
        evidence_id="EV_X",
        source_id="SRC_INCOMPLETE",
        instrument="vln",
        technique="artificial_harmonic",
        page_start=1,
        paraphrased_claim="x",
        quantitative_or_qualitative="quantitative",
        reported_value=1.0,
        original_unit="dimensionless",
        directness="direct_same_instrument_same_technique",
        density_mapping_status="direct_same_metric",
        curator_verification_status="validated",
        extraction_method="manual_extraction_from_table",
    )
    param = {
        "parameter_id": "P_INCOMPLETE",
        "parameter_name": "x",
        "instrument": "vln",
        "technique": "artificial_harmonic",
        "model_component": "density_transform",
        "source_ids": ["SRC_INCOMPLETE"],
        "evidence_ids": ["EV_X"],
        "direct_or_transferred": "direct",
        "reported_value": 1.1,
        "active_for_density_prediction": True,
        "density_mapping_status": "direct_same_metric",
        "operation_type": "multiplicative_ratio",
        "numerical_scale": "raw_density",
        "unit": "dimensionless",
        "evidence_grade": "B",
        "confidence_level": "low",
    }
    resolved = resolve_parameter_provenance(param, SourceRegistry([src]), [ext])
    assert provenance_allows_density_activation(resolved) is False


def test_07_unverified_extract_cannot_activate():
    src = LiteratureSource(
        source_id="SRC_OK",
        source_type="peer_reviewed_journal",
        full_citation="Ok, A. (2020). Title. Journal, 1(1), 1-2.",
        authors=["Ok, A."],
        year=2020,
        title="Title",
        journal_or_publisher="Journal",
        volume="1",
        pages="1-2",
        DOI="10.0/ok",
        local_file_path=str(PACKAGE_ROOT / "configs" / "literature_sources.yaml"),
        evidence_status="verified_local_source",
    )
    ext = EvidenceExtract(
        evidence_id="EV_UNVER",
        source_id="SRC_OK",
        instrument="vln",
        technique="sul_ponticello",
        page_start=1,
        paraphrased_claim="x",
        quantitative_or_qualitative="quantitative",
        reported_value=1.1,
        original_unit="dimensionless",
        directness="direct_same_instrument_same_technique",
        density_mapping_status="direct_same_metric",
        curator_verification_status="unverified",
        extraction_method="manual_extraction_from_table",
    )
    param = {
        "parameter_id": "P_UNVER",
        "instrument": "vln",
        "technique": "sul_ponticello",
        "model_component": "density_transform",
        "source_ids": ["SRC_OK"],
        "evidence_ids": ["EV_UNVER"],
        "direct_or_transferred": "direct",
        "reported_value": 1.1,
        "active_for_density_prediction": True,
        "density_mapping_status": "direct_same_metric",
        "operation_type": "multiplicative_ratio",
    }
    resolved = resolve_parameter_provenance(param, SourceRegistry([src]), [ext])
    assert provenance_allows_density_activation(resolved) is False


def test_08_indirect_proxy_remains_inactive():
    param = _meyer_param()
    assert param["density_mapping_status"] == "indirect_proxy"
    assert param["active_for_density_prediction"] is False
    assert meyer_dynamic_range_is_not_density(param)
    report = validate_all_parameters(
        PACKAGE_ROOT / "configs" / "literature_parameters.yaml", strict=False
    )
    meyer_row = next(
        r for r in report["results"] if r["parameter_id"] == "MEYER_VLN_HARMONIC_DYNAMIC_RANGE"
    )
    assert "indirect_density_proxy" in meyer_row["reasons"] or not meyer_row["active_for_density_prediction"]


def test_09_inactive_parameter_does_not_crash_unrelated_predictions():
    # Must not raise despite Meyer lacking embedded full_citation/extraction_method
    report = validate_all_parameters(
        PACKAGE_ROOT / "configs" / "literature_parameters.yaml", strict=False
    )
    assert report["ok"] is True
    result = estimate_cell(
        instrument="vln",
        technique="sul_ponticello",
        note="A4",
        dynamic="mf",
        ordinary_density=20.0,
        parameters=report["parameters"],
        n_draws=50,
        random_seed=1,
    )
    assert result.estimated_density is None
    assert "not_estimable" in result.estimation_status


def test_10_required_active_unresolved_fails_strict():
    with pytest.raises(ProvenanceError, match="unresolved_scientific_provenance"):
        estimate_cell(
            instrument="vln",
            technique="sul_ponticello",
            note="A4",
            dynamic="mf",
            ordinary_density=20.0,
            parameters=[
                {
                    "parameter_id": "ACTIVE_BROKEN",
                    "instrument": "vln",
                    "technique": "sul_ponticello",
                    "model_component": "density_transform",
                    "source_ids": ["MISSING_SOURCE"],
                    "evidence_ids": ["MISSING_EV"],
                    "direct_or_transferred": "direct",
                    "reported_value": 1.1,
                    "active_for_density_prediction": True,
                    "density_mapping_status": "direct_same_metric",
                    "operation_type": "multiplicative_ratio",
                    "numerical_scale": "raw_density",
                    "unit": "dimensionless",
                }
            ],
            n_draws=10,
            random_seed=1,
            strict=True,
        )


def test_11_empty_strings_do_not_satisfy_provenance():
    param = dict(_meyer_param())
    param["source_ids"] = [""]
    param["source_id"] = ""
    param["full_citation"] = ""
    param["extraction_method"] = "unknown"
    resolved = resolve_parameter_provenance(
        param, SourceRegistry.from_yaml(), load_extracts()
    )
    assert resolved.ok is False


def test_12_source_id_source_ids_migration_deterministic():
    a = normalize_source_ids({"source_id": "MEYER_ACOUSTICS"})
    b = normalize_source_ids({"source_ids": ["MEYER_ACOUSTICS"]})
    c = normalize_source_ids({"source_ids": '["MEYER_ACOUSTICS"]'})
    assert a == b == c == ["MEYER_ACOUSTICS"]


def test_13_meyer_dynamic_range_not_interpreted_as_density():
    param = _meyer_param()
    assert meyer_dynamic_range_is_not_density(param)
    result = estimate_cell(
        instrument="vln",
        technique="artificial_harmonic",
        note="A5",
        dynamic="mf",
        ordinary_density=20.0,
        parameters=[param],
        n_draws=100,
        random_seed=1,
    )
    assert result.estimated_density is None


def test_14_pipeline_produces_explicit_activation_failure_record():
    package = ingest_evidence_package(dry_run=True)
    failures = {r["parameter_id"]: r for r in package.activation_failures}
    assert "MEYER_VLN_HARMONIC_DYNAMIC_RANGE" in failures
    reasons = failures["MEYER_VLN_HARMONIC_DYNAMIC_RANGE"]["failure_reasons"]
    assert "indirect_density_proxy" in reasons
    # Rebuild outputs to ensure CSV written
    package = ingest_evidence_package(dry_run=False, overwrite=True)
    assert (PACKAGE_ROOT / "outputs" / "literature" / "inactive_parameters.csv").exists()
    assert (PACKAGE_ROOT / "outputs" / "literature" / "parameter_activation_failures.csv").exists()
    text = (
        PACKAGE_ROOT / "outputs" / "literature" / "parameter_activation_failures.csv"
    ).read_text(encoding="utf-8")
    assert "MEYER_VLN_HARMONIC_DYNAMIC_RANGE" in text
    assert "indirect_density_proxy" in text
