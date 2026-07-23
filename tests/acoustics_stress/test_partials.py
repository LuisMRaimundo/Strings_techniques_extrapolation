"""Partial salience and pitch-component count."""

from __future__ import annotations

import pytest

from string_technique_model.descriptors.models import AnalysisProfile, load_analysis_profile
from string_technique_model.descriptors.partials import (
    compute_partial_salience,
    compute_pitch_component_count,
)
from string_technique_model.testing.descriptor_asserts import assert_provenance
from string_technique_model.testing.signal_generators import generate_signal

pytestmark = pytest.mark.acoustics_stress


def _profile(**partial_overrides: object) -> AnalysisProfile:
    data = load_analysis_profile().model_dump()
    data["partials"] = {**data["partials"], **partial_overrides}
    return AnalysisProfile.model_validate(data)


@pytest.mark.mathematical_exact
def test_one_component() -> None:
    sig = generate_signal("pure_sine", duration_s=0.5, frequency_hz=1000.0)
    count = compute_pitch_component_count(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=_profile(min_separation_hz=30.0, amplitude_threshold_ratio=0.05),
    )
    sal = compute_partial_salience(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=_profile(min_separation_hz=30.0, amplitude_threshold_ratio=0.05),
    )
    assert_provenance(count)
    assert_provenance(sal)
    assert int(count.value) == 1
    assert len(sal.value) == 1
    assert abs(sal.value[0]["salience"] - 1.0) < 1e-9
    assert sal.extras["proxy_warning"] == "not_physical_cello_multiphonic"


@pytest.mark.mathematical_exact
def test_two_separated_components() -> None:
    sig = generate_signal("two_tone", duration_s=0.5, f1_hz=400.0, f2_hz=1200.0, a1=0.5, a2=0.5)
    count = compute_pitch_component_count(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=_profile(min_separation_hz=40.0),
    )
    assert int(count.value) == 2


@pytest.mark.metamorphic
def test_octave_related_components_with_and_without_equivalence() -> None:
    sig = generate_signal("two_tone", duration_s=0.5, f1_hz=220.0, f2_hz=440.0, a1=0.5, a2=0.5)
    raw = compute_pitch_component_count(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=_profile(octave_equivalence=False, min_separation_hz=20.0),
    )
    eq = compute_pitch_component_count(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=_profile(octave_equivalence=True, min_separation_hz=20.0),
    )
    assert int(raw.value) == 2
    assert int(eq.value) == 1


@pytest.mark.metamorphic
def test_closely_spaced_beating_components() -> None:
    sig = generate_signal("beating_pair", duration_s=0.5, f1_hz=440.0, f2_hz=444.0)
    # With large min_separation, beating pair collapses to one peak group.
    wide = compute_pitch_component_count(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=_profile(min_separation_hz=20.0),
    )
    narrow = compute_pitch_component_count(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=_profile(min_separation_hz=1.0, amplitude_threshold_ratio=0.01),
    )
    assert int(wide.value) <= int(narrow.value)


@pytest.mark.metamorphic
def test_weak_component_below_threshold() -> None:
    sig = generate_signal("two_tone", duration_s=0.5, f1_hz=500.0, f2_hz=1500.0, a1=1.0, a2=0.001)
    count = compute_pitch_component_count(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=_profile(amplitude_threshold_ratio=0.05, min_separation_hz=30.0),
    )
    assert int(count.value) == 1


@pytest.mark.metamorphic
def test_noise_contamination_and_missing_fundamental() -> None:
    noisy = generate_signal(
        "harmonic_plus_noise", duration_s=0.5, frequency_hz=220.0, n_harmonics=5, noise_level=0.3, seed=3
    )
    mf = generate_signal("missing_fundamental", duration_s=0.5, frequency_hz=220.0, n_harmonics=6)
    profile = _profile(amplitude_threshold_ratio=0.05, min_separation_hz=25.0)
    c_n = compute_pitch_component_count(
        noisy.samples, measurement_domain="radiated_audio", sample_rate=noisy.sample_rate_hz, profile=profile
    )
    c_mf = compute_pitch_component_count(
        mf.samples, measurement_domain="radiated_audio", sample_rate=mf.sample_rate_hz, profile=profile
    )
    assert int(c_n.value) >= 1
    assert int(c_mf.value) >= 2
    # Must not be labelled as physical cello multiphonics
    sal = compute_partial_salience(
        mf.samples, measurement_domain="radiated_audio", sample_rate=mf.sample_rate_hz, profile=profile
    )
    assert "not_physical_cello_multiphonic" in sal.extras["proxy_warning"]
