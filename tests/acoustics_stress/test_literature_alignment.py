"""Literature oracle / identity / secondary-synthesis gating."""

from __future__ import annotations

import pytest

from string_technique_model.literature.package_ingestion import ingest_evidence_package
from string_technique_model.literature.source_identity import load_source_identity_registry
from string_technique_model.literature.source_registry import SourceRegistry
from string_technique_model.testing.literature_oracles import validate_benchmark_sources_against_identity

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.provenance
@pytest.mark.literature_bounded
def test_benchmark_sources_pass_identity_gate(literature_cases) -> None:
    result = validate_benchmark_sources_against_identity(literature_cases)
    assert result["ok"] is True, result["errors"]


@pytest.mark.provenance
def test_rejected_archive_files_not_verified_sources() -> None:
    identity = load_source_identity_registry()
    rejected = identity.by_status("rejected_file_identity_mismatch")
    assert rejected
    for entry in rejected:
        assert entry.associated_source_id is None or entry.identity_match is False


@pytest.mark.provenance
def test_fallowfield_duplicate_not_handbook() -> None:
    identity = load_source_identity_registry()
    dup = identity.entries["ID_FALLOWFIELD_2009_CLAIMED"]
    assert dup.validation_status == "duplicate_file"
    assert dup.duplicate_of == "ID_FALLOWFIELD_2020_TEMPO"


@pytest.mark.unsupported_extrapolation
@pytest.mark.benchmark
def test_benchmark_i_no_active_density_parameters() -> None:
    result = ingest_evidence_package(dry_run=True)
    active = [d for d in result.decisions if getattr(d, "active", False)]
    assert active == []


@pytest.mark.unsupported_extrapolation
def test_secondary_synthesis_soa_verified_but_not_activating_ewsd() -> None:
    sources = SourceRegistry.from_yaml()
    soa = sources.get("SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART")
    assert soa.evidence_status == "verified_local_source"
    assert getattr(soa, "evidence_class", None) == "secondary_synthesis"
    result = ingest_evidence_package(dry_run=True)
    assert not any(getattr(d, "active", False) for d in result.decisions)
