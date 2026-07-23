"""Phase 3 — literature evidence framework with curated Meyer package."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.literature.corpus import (
    add_extract,
    ensure_corpus_directories,
    local_corpus_status_markdown,
    register_source,
    scan_corpus,
)
from string_technique_model.literature.domain import (
    ALLOWED_INSTRUMENTS,
    ALLOWED_TECHNIQUES,
    all_instrument_technique_cells,
)
from string_technique_model.literature.evidence_matrix import build_evidence_matrix
from string_technique_model.literature.extracts import EvidenceExtract
from string_technique_model.literature.pipeline import build_literature_layer
from string_technique_model.literature.source_registry import LiteratureSource, SourceRegistry


def test_sixteen_cells_structurally_complete():
    result = build_literature_layer(dry_run=True)
    assert len(result.matrix_rows) == 16
    assert len(all_instrument_technique_cells()) == 16


def test_curated_package_raises_some_grades_from_validated_extracts():
    result = build_literature_layer(dry_run=True)
    grades = {f"{r['instrument']}/{r['technique']}": r["evidence_grade"] for r in result.matrix_rows}
    assert grades["vln/artificial_harmonic"] in {"B", "C"}
    assert grades["vln/con_sordino"] in {"B", "C"}
    assert grades["vln/sul_ponticello"] in {"B", "C", "D"}
    # No density metric evidence yet
    assert all(r["direct_density_metric_evidence"] is False for r in result.matrix_rows)


def test_only_four_instruments_and_techniques():
    result = build_literature_layer(dry_run=True)
    assert set(r["instrument"] for r in result.matrix_rows) == ALLOWED_INSTRUMENTS
    assert set(r["technique"] for r in result.matrix_rows) == ALLOWED_TECHNIQUES


def test_bibliographic_citation_alone_does_not_activate_evidence():
    # Schelleng is registered as pending_local_source with complete citation but no extracts
    registry = SourceRegistry.from_yaml()
    schelleng = registry.get("SRC_SCHELLENG_1973")
    assert schelleng.evidence_status == "pending_local_source"
    matrix = build_evidence_matrix(registry, [], mode="curated_package")
    vln_sp = next(
        r for r in matrix if r["instrument"] == "vln" and r["technique"] == "sul_ponticello"
    )
    assert vln_sp["evidence_grade"] == "NA"
    assert vln_sp["source_ids"] == []


def test_pdf_alone_does_not_activate_evidence(tmp_path: Path):
    ensure_corpus_directories()
    pdf = PACKAGE_ROOT / "literature" / "corpus" / "articles" / "_test_dummy_source.txt"
    pdf.write_text("placeholder corpus file — not scientific evidence\n", encoding="utf-8")
    try:
        scan = scan_corpus()
        assert scan.n_files_found >= 1
        # Dummy file must not create extracts or density activation
        result = build_literature_layer(dry_run=True)
        assert result.n_active_density_parameters == 0
        assert all(r["direct_density_metric_evidence"] is False for r in result.matrix_rows)
    finally:
        if pdf.exists():
            pdf.unlink()


def test_unverified_extract_does_not_activate_evidence():
    verified = LiteratureSource(
        source_id="SRC_TEST_LOCAL",
        source_type="peer_reviewed_journal",
        full_citation="Test, A. (2020). Title. Journal, 1(1), 1-2.",
        authors=["Test, A."],
        year=2020,
        title="Title",
        journal_or_publisher="Journal",
        volume="1",
        pages="1-2",
        DOI="10.0/test-unverified",
        local_file_path=str(PACKAGE_ROOT / "configs" / "literature_sources.yaml"),
        evidence_status="verified_local_source",
        instruments_covered=["vln"],
        techniques_covered=["sul_ponticello"],
    )
    reg = SourceRegistry([verified])
    ext = EvidenceExtract(
        source_id="SRC_TEST_LOCAL",
        instrument="vln",
        technique="sul_ponticello",
        paraphrased_claim="Unverified claim",
        quantitative_or_qualitative="qualitative",
        directness="qualitative_performance_description",
        page_start=10,
        curator_verification_status="unverified",
        original_variable_name="spectral_character",
    )
    ext.assign_deterministic_id()
    matrix = build_evidence_matrix(reg, [ext], mode="verified_local")
    cell = next(r for r in matrix if r["instrument"] == "vln" and r["technique"] == "sul_ponticello")
    assert cell["evidence_grade"] == "NA"
    assert cell["source_ids"] == []


def test_only_validated_extract_from_verified_source_alters_cell():
    verified = LiteratureSource(
        source_id="SRC_TEST_VALID",
        source_type="peer_reviewed_journal",
        full_citation="Test, A. (2020). Title. Journal, 1(1), 1-2.",
        authors=["Test, A."],
        year=2020,
        title="Title",
        journal_or_publisher="Journal",
        volume="1",
        pages="1-2",
        DOI="10.0/test-valid",
        local_file_path=str(PACKAGE_ROOT / "configs" / "literature_sources.yaml"),
        evidence_status="verified_local_source",
        instruments_covered=["vln"],
        techniques_covered=["sul_ponticello"],
    )
    reg = SourceRegistry([verified])
    ext = EvidenceExtract(
        source_id="SRC_TEST_VALID",
        instrument="vln",
        technique="sul_ponticello",
        paraphrased_claim="Validated qualitative constraint",
        quantitative_or_qualitative="qualitative",
        directness="qualitative_performance_description",
        page_start=11,
        curator_verification_status="validated",
        original_variable_name="spectral_character",
        canonical_variable_name="spectral_character",
    )
    ext.assign_deterministic_id()
    matrix = build_evidence_matrix(reg, [ext], mode="verified_local")
    cell = next(r for r in matrix if r["instrument"] == "vln" and r["technique"] == "sul_ponticello")
    assert cell["evidence_grade"] == "D"
    assert cell["estimation_status"] == "qualitative_constraints_only"
    assert "SRC_TEST_VALID" in cell["source_ids"]
    assert cell["evidence_ids"]
    assert cell["evidence_last_evaluated_utc"]


def test_no_active_density_parameter_without_direct_mapping():
    result = build_literature_layer(dry_run=True)
    assert result.n_active_density_parameters == 0
    assert not any(r.get("is_active") for r in result.parameter_rows)


def test_qualitative_extracts_cannot_activate_numerical_parameters():
    result = build_literature_layer(dry_run=True)
    for row in result.parameter_rows:
        if row.get("parameter_status") == "qualitative_only":
            assert row.get("is_active") is False


def test_local_corpus_status_distinguishes_metadata_from_books():
    ensure_corpus_directories()
    scan = scan_corpus()
    md = local_corpus_status_markdown(scan)
    # Curator metadata may exist; books PDFs may not.
    compact = " ".join(md.split())
    assert "Absence of evidence in the local corpus must not be interpreted as" in compact
    assert "File presence alone does not activate evidence grades" in compact or (
        "No local literature corpus was available" in compact
    )
    build_literature_layer(overwrite=True)
    status_path = PACKAGE_ROOT / "reports" / "local_corpus_status.md"
    assert status_path.exists()


def test_no_density_predictions_generated():
    result = build_literature_layer(dry_run=True)
    for row in result.matrix_rows:
        assert "estimated_density" not in row
        assert "predicted_density" not in row
    from string_technique_model.estimate import estimate_cell

    out = estimate_cell(
        instrument="vln",
        technique="sul_ponticello",
        note="A4",
        dynamic="mf",
        ordinary_density=20.0,
        parameters=[],
        n_draws=10,
        random_seed=1,
        metric=None,
        unsupported_reasons=[],
    )
    assert out.estimated_density is None
    assert "not_estimable" in out.estimation_status


def test_scan_corpus_never_auto_extracts():
    scan = scan_corpus()
    assert "does not create evidence extracts" in " ".join(scan.notes).lower() or any(
        "does not" in n.lower() for n in scan.notes
    )
    extracts = yaml.safe_load(
        (PACKAGE_ROOT / "configs" / "literature_evidence_extracts.yaml").read_text(encoding="utf-8")
    )
    # Curator package may contain extracts; scan must not invent additional ones.
    assert isinstance(extracts.get("extracts"), list)
    for e in extracts.get("extracts") or []:
        assert e.get("extraction_method") in {None, "curator_package", "manual", "pdf_page_verified"}


def test_register_source_does_not_activate_evidence(tmp_path: Path):
    f = tmp_path / "demo.txt"
    f.write_text("local file placeholder", encoding="utf-8")
    result = register_source(
        source_id="SRC_TMP_DEMO",
        file_path=f,
        full_citation="Demo, A. (2020). Demo. Journal, 1(1), 1-2.",
        title="Demo",
        year=2020,
        authors=["Demo, A."],
        journal_or_publisher="Journal",
        instruments=["vln"],
        techniques=["sul_ponticello"],
        dry_run=True,
    )
    assert result["evidence_activated"] is False
    assert result["entry"]["evidence_status"] == "pending_verification"


def test_add_extract_requires_location_and_units():
    with pytest.raises(ValueError, match="Exact location"):
        add_extract(
            source_id="SRC_SCHELLENG_1973",
            instrument="vln",
            technique="sul_ponticello",
            paraphrased_claim="x",
            quantitative_or_qualitative="qualitative",
            measured_variable="y",
            directness="qualitative_performance_description",
            curator_verification_status="unverified",
            dry_run=True,
        )
    with pytest.raises(ValueError, match="unit"):
        add_extract(
            source_id="SRC_SCHELLENG_1973",
            instrument="vln",
            technique="sul_ponticello",
            paraphrased_claim="x",
            quantitative_or_qualitative="quantitative",
            measured_variable="y",
            directness="direct_same_instrument_same_technique",
            curator_verification_status="unverified",
            page_start=1,
            dry_run=True,
        )


def test_readme_states_absence_is_not_evidence_of_absence():
    readme = (PACKAGE_ROOT / "README.md").read_text(encoding="utf-8")
    assert (
        "Absence of evidence in the local corpus must not be interpreted as"
        in readme
    )


def test_evidence_ids_exclude_timestamps():
    ext = EvidenceExtract(
        source_id="SRC_X",
        instrument="vln",
        technique="sul_ponticello",
        paraphrased_claim="Same",
        quantitative_or_qualitative="qualitative",
        directness="qualitative_performance_description",
        page_start=1,
        curator_verification_status="unverified",
        evidence_last_evaluated_utc="2020-01-01T00:00:00+00:00",
    )
    a = ext.assign_deterministic_id()
    b = EvidenceExtract(
        source_id="SRC_X",
        instrument="vln",
        technique="sul_ponticello",
        paraphrased_claim="Same",
        quantitative_or_qualitative="qualitative",
        directness="qualitative_performance_description",
        page_start=1,
        curator_verification_status="unverified",
        evidence_last_evaluated_utc="2099-01-01T00:00:00+00:00",
    ).assign_deterministic_id()
    assert a == b


def test_corpus_directories_exist():
    ensure_corpus_directories()
    root = PACKAGE_ROOT / "literature" / "corpus"
    for name in ("books", "articles", "theses", "reports", "metadata"):
        assert (root / name).is_dir()
