"""Source identity validation — reject filename-only claims."""

from __future__ import annotations

from string_technique_model.literature.source_identity import (
    load_source_identity_registry,
    write_source_identity_report,
)
from string_technique_model.literature.source_registry import SourceRegistry


def test_registry_loads_and_has_three_books() -> None:
    reg = load_source_identity_registry()
    ids = {e.entry_id for e in reg.list_entries()}
    assert "ID_MEYER_2009" in ids
    assert "ID_FLETCHER_ROSSING_PHYSICS" in ids
    assert "ID_ROSSING_SCIENCE_STRINGS_2010" in ids
    for entry_id in ("ID_MEYER_2009", "ID_FLETCHER_ROSSING_PHYSICS", "ID_ROSSING_SCIENCE_STRINGS_2010"):
        entry = reg.entries[entry_id]
        assert entry.validation_status == "verified_identity"
        assert entry.identity_match is True
        assert entry.page_count and entry.page_count > 100
        assert entry.deposited_path and entry.deposited_path.startswith("literature/corpus/books/")


def test_duplicate_pdf_detection_by_hash() -> None:
    reg = load_source_identity_registry()
    dups = reg.detect_hash_duplicates()
    assert dups
    hashes = {h for h, _ in dups}
    fallow = reg.entries["ID_FALLOWFIELD_2020_TEMPO"].file_hash_sha256
    assert fallow in hashes
    assert reg.entries["ID_FALLOWFIELD_2009_CLAIMED"].validation_status == "duplicate_file"
    assert reg.entries["ID_FALLOWFIELD_2009_CLAIMED"].duplicate_of == "ID_FALLOWFIELD_2020_TEMPO"


def test_identity_mismatch_rejection() -> None:
    reg = load_source_identity_registry()
    berio = reg.entries["ID_BERIO_CLAIMED"]
    hann = reg.entries["ID_HANN_CLAIMED"]
    rimsky = reg.entries["ID_RIMSKY_CLAIMED"]
    assert berio.validation_status == "rejected_file_identity_mismatch"
    assert hann.validation_status == "rejected_file_identity_mismatch"
    assert rimsky.validation_status == "rejected_file_identity_mismatch"
    assert berio.identity_match is False


def test_insufficient_metadata_messina() -> None:
    reg = load_source_identity_registry()
    messina = reg.entries["ID_MESSINA_CLAIMED"]
    assert messina.validation_status == "insufficient_metadata"


def test_internal_doi_validation() -> None:
    reg = load_source_identity_registry()
    assert reg.doi_present_and_nonempty("ID_SCHOONDERWALDT_2009")
    assert reg.doi_present_and_nonempty("ID_EVANGELISTA_FREIRE_2025")
    assert reg.doi_present_and_nonempty("ID_LOSTANLEN_2018")
    assert reg.doi_present_and_nonempty("ID_FLETCHER_ROSSING_PHYSICS")
    assert reg.doi_present_and_nonempty("ID_ROSSING_SCIENCE_STRINGS_2010")


def test_rejection_of_filename_only_source_identity() -> None:
    reg = load_source_identity_registry()
    # Mismatched filename claims must be rejected as filename-only authority
    assert (
        reg.reject_filename_only_claim(
            "Berio_(1976)_Sequenza VIII for violin.pdf"
        )
        is True
    )
    assert (
        reg.reject_filename_only_claim(
            "Hann_(2015)_The influence of historic violin treatises on modern teaching and performance practices.pdf"
        )
        is True
    )
    # Verified Meyer is not rejected once internal identity is present
    assert (
        reg.reject_filename_only_claim(
            "IMP_Acoustics and the Performance of music_(Jürgen Meyer) (z-lib.org).pdf"
        )
        is False
    )


def test_stowell_partial_match_registers_actual_publication() -> None:
    reg = load_source_identity_registry()
    stowell = reg.entries["ID_STOWELL_CLAIMED_1978"]
    assert stowell.validation_status == "partial_identity_match"
    assert stowell.associated_source_id == "SRC_STOWELL_CAMBRIDGE_TECHNIQUE_PERFORMING_PRACTICE"
    sources = SourceRegistry.from_yaml()
    src = sources.get("SRC_STOWELL_CAMBRIDGE_TECHNIQUE_PERFORMING_PRACTICE")
    assert "thesis" not in (src.title or "").lower()
    assert src.local_file_path


def test_meyer_upgraded_to_verified_local_source() -> None:
    sources = SourceRegistry.from_yaml()
    meyer = sources.get("MEYER_ACOUSTICS")
    assert meyer.evidence_status == "verified_local_source"
    assert meyer.year == 2009
    assert meyer.ISBN == "978-0-387-09516-5"
    assert meyer.may_support_parameters()


def test_write_identity_report(tmp_path) -> None:
    out = write_source_identity_report(tmp_path / "source_identity_validation.md")
    text = out.read_text(encoding="utf-8")
    assert "ID_MEYER_2009" in text
    assert "ID_FLETCHER_ROSSING_PHYSICS" in text
    assert "rejected_file_identity_mismatch" in text
