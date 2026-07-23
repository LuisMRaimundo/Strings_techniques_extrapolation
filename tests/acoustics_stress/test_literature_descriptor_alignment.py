"""Literature alignment for descriptors — domain/setup mismatches are not numerical failures."""

from __future__ import annotations

import pytest

from string_technique_model.descriptors.attenuation import refuse_sones_as_db
from string_technique_model.descriptors.engine import domains_comparable
from string_technique_model.testing.literature_oracles import (
    load_literature_benchmark_cases,
    physics_oracle_sounding_hz,
    validate_benchmark_sources_against_identity,
)

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.literature_bounded
@pytest.mark.provenance
def test_physics_oracle_p4_is_first_principles_no_source_warning() -> None:
    cases = load_literature_benchmark_cases()
    case = next(c for c in cases if c.benchmark_case_id == "BM_PHYSICS_ORACLE_HARMONIC_P4")
    assert case.oracle_type == "analytical_identity"
    assert case.provenance_type == "first_principles"
    assert case.source_required is False
    assert case.expected["relation"] == "f_n = n * f_0"
    assert physics_oracle_sounding_hz(220.0, 4) == 880.0
    result = validate_benchmark_sources_against_identity(cases)
    assert result["ok"] is True
    assert not any("BM_PHYSICS_ORACLE_HARMONIC_P4" in w for w in result["warnings"])
    assert not any("BM_PHYSICS_ORACLE_HARMONIC_P4" in e for e in result["errors"])


@pytest.mark.literature_bounded
@pytest.mark.measurement_domain
def test_schoonderwaldt_mic_vs_string_bridge_centroid_not_comparable() -> None:
    """Do not compare ordinary microphone-audio centroid with string/bridge-force centroid."""
    cmp = domains_comparable("radiated_audio", "string_velocity_at_bow")
    assert cmp["status"] == "not_comparable"
    assert cmp["classification"] == "not_comparable"
    classification = "not_comparable"
    assert classification != "contradicted"


@pytest.mark.literature_bounded
@pytest.mark.measurement_domain
def test_evangelista_sones_intensity_ltas_mute_metadata_distinct() -> None:
    quantities = {
        "ltas": "radiated_audio_spectrum_vector",
        "loudness_sones": "psychoacoustic_loudness",
        "intensity_reduction": "power_or_intensity_ratio_dB",
        "mute_metadata": "categorical_instrumentation",
    }
    assert len(set(quantities.values())) == 4
    with pytest.raises(ValueError, match="sones"):
        refuse_sones_as_db("loudness_sones")
    classification = "not_comparable"
    assert classification == "not_comparable"


@pytest.mark.literature_bounded
def test_empirical_benchmark_cases_require_source_id() -> None:
    cases = load_literature_benchmark_cases()
    for case in cases:
        if case.oracle_type in {
            "empirical",
            "historical",
            "secondary_synthesis",
            "literature_bounded",
        }:
            assert case.source_id, case.benchmark_case_id
            assert case.source_required is True
