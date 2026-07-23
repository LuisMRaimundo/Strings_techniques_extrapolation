"""Descriptor registry, provenance, and unsupported-descriptor scope safeguards."""

from __future__ import annotations

import pytest

from string_technique_model.descriptors import (
    clear_descriptor_registry_cache,
    compute_descriptor,
    implemented_descriptor_ids,
    list_implemented_descriptors,
    load_descriptor_registry,
)
from string_technique_model.testing.descriptor_asserts import assert_provenance
from string_technique_model.testing.signal_generators import SUPPORTED_SIGNAL_KINDS, generate_signal

pytestmark = pytest.mark.acoustics_stress

IMPLEMENTED = {
    "DESC_SPECTRAL_CENTROID",
    "DESC_SPECTRAL_SLOPE",
    "DESC_HNR",
    "DESC_SPECTRAL_FLUX",
    "DESC_FRAME_SPECTRAL_VARIANCE",
    "DESC_LTAS",
    "DESC_PARTIAL_SALIENCE",
    "DESC_PITCH_COMPONENT_COUNT",
    "DESC_ABSOLUTE_ATTENUATION",
}


@pytest.fixture(autouse=True)
def _clear_registry_cache() -> None:
    clear_descriptor_registry_cache()
    yield
    clear_descriptor_registry_cache()


@pytest.mark.regression
def test_implemented_descriptors_registered() -> None:
    specs = list_implemented_descriptors()
    ids = {s.descriptor_id for s in specs}
    assert IMPLEMENTED <= ids
    # Audio dispatch excludes typed attenuation (scalar ratio helpers, not STFT).
    assert "DESC_SPECTRAL_CENTROID" in implemented_descriptor_ids()
    assert "DESC_ABSOLUTE_ATTENUATION" not in implemented_descriptor_ids()


@pytest.mark.regression
def test_unsupported_descriptors_remain_unimplemented() -> None:
    reg = load_descriptor_registry()
    for did in (
        "DESC_LOUDNESS",
        "DESC_TEMPORAL_MODULATION",
        "DESC_ATTACK_TIME",
        "DESC_BRIDGE_MOBILITY",
    ):
        spec = reg.get(did)
        assert spec is not None
        assert spec.implemented is False


@pytest.mark.unsupported_extrapolation
def test_unsupported_descriptor_scope_safeguard_not_numerical_validation() -> None:
    """descriptor unavailable — scope safeguard passed (not numerical acoustic validation)."""
    reg = load_descriptor_registry()
    loud = reg.get("DESC_LOUDNESS")
    assert loud is not None and loud.implemented is False
    with pytest.raises(KeyError, match="no numerical implementation"):
        compute_descriptor(
            "DESC_LOUDNESS",
            generate_signal("pure_sine", duration_s=0.1).samples,
            measurement_domain="radiated_audio",
        )


@pytest.mark.unsupported_extrapolation
def test_descriptor_values_must_not_be_relabelled_ewsd() -> None:
    reg = load_descriptor_registry()
    for spec in reg.all():
        compat = str(getattr(spec, "ewsd_compatibility", "") or "")
        assert "incompatible" in compat.lower()


@pytest.mark.metamorphic
def test_synthetic_fixtures_generate() -> None:
    for kind in SUPPORTED_SIGNAL_KINDS:
        if kind in {"nan_contaminated", "inf_contaminated"}:
            sig = generate_signal(kind, duration_s=0.05, seed=0)
            assert len(sig.samples) > 0
            continue
        sig = generate_signal(kind, duration_s=0.05, seed=0)
        if kind not in {"silence"}:
            sig.assert_finite()


@pytest.mark.regression
def test_compute_descriptor_exposes_provenance_fields() -> None:
    sig = generate_signal("pure_sine", duration_s=0.25, frequency_hz=1000.0)
    result = compute_descriptor(
        "DESC_SPECTRAL_CENTROID",
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
    )
    assert_provenance(result)
