"""Long-term average spectrum — vector descriptor object."""

from __future__ import annotations

import pytest
import yaml

from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.descriptors.ltas import compute_ltas, ltas_comparable
from string_technique_model.descriptors.models import AnalysisProfile, load_analysis_profile
from string_technique_model.testing.descriptor_asserts import assert_provenance
from string_technique_model.testing.signal_generators import generate_signal

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.mathematical_exact
def test_ltas_is_vector_not_scalar() -> None:
    sig = generate_signal("harmonic_sum", duration_s=0.5, frequency_hz=196.0, n_harmonics=6)
    result = compute_ltas(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=load_analysis_profile(),
    )
    assert_provenance(result)
    assert isinstance(result.value, dict)
    assert "frequencies_hz" in result.value and "spectrum" in result.value
    assert len(result.value["spectrum"]) == len(result.value["frequencies_hz"])
    assert result.extras["is_vector_descriptor"] is True
    assert result.unit == "power_linear_mean"
    assert result.normalization == "none"


@pytest.mark.measurement_domain
def test_normalized_vs_unnormalized_ltas_not_comparable() -> None:
    sig = generate_signal("pure_sine", duration_s=0.4, frequency_hz=880.0)
    base = load_analysis_profile().model_dump()
    a = AnalysisProfile.model_validate({**base, "ltas": {**base["ltas"], "normalize": False}})
    b = AnalysisProfile.model_validate({**base, "ltas": {**base["ltas"], "normalize": True}})
    r_a = compute_ltas(sig.samples, measurement_domain="radiated_audio", sample_rate=sig.sample_rate_hz, profile=a)
    r_b = compute_ltas(sig.samples, measurement_domain="radiated_audio", sample_rate=sig.sample_rate_hz, profile=b)
    cmp = ltas_comparable(r_a, r_b)
    assert cmp["status"] == "not_comparable"
    assert "normalization" in cmp["reason"]


@pytest.mark.literature_bounded
def test_evangelista_ltas_profile_is_source_stub_not_silently_comparable() -> None:
    path = PACKAGE_ROOT / "configs" / "analysis_profiles" / "evangelista_freire_2025_ltas.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["status"] == "metadata_stub"
    params = data["analysis_parameters"]
    # Verified paper identity exists, but analysis settings remain unresolved → not comparable.
    unresolved = [
        params.get("sample_rate_hz"),
        params.get("window_type"),
        params.get("fft_size"),
        params.get("averaging_method"),
    ]
    assert any(v is None for v in unresolved)
    classification = "source_data_insufficient"
    assert classification == "source_data_insufficient"


@pytest.mark.measurement_domain
def test_ltas_domain_mismatch_not_comparable() -> None:
    sig = generate_signal("pure_sine", duration_s=0.3, frequency_hz=440.0)
    profile = load_analysis_profile()
    a = compute_ltas(sig.samples, measurement_domain="radiated_audio", sample_rate=sig.sample_rate_hz, profile=profile)
    b = compute_ltas(sig.samples, measurement_domain="bridge_force", sample_rate=sig.sample_rate_hz, profile=profile)
    cmp = ltas_comparable(a, b)
    assert cmp["status"] == "not_comparable"
    assert cmp["reason"] == "measurement_domain_mismatch"
