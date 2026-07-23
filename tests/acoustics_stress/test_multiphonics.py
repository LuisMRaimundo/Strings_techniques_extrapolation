"""Multiphonic representation stress tests (Fallowfield scope)."""

from __future__ import annotations

import pytest

from string_technique_model.production.models import MultiphonicInstruction
from string_technique_model.production.multiphonics import assert_distinct_from_harmonics
from string_technique_model.testing.signal_generators import generate_signal

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.literature_bounded
@pytest.mark.benchmark
def test_benchmark_g_style_multiphonic_distinct_from_harmonics() -> None:
    assert_distinct_from_harmonics("multiphonic")
    with pytest.raises(ValueError):
        assert_distinct_from_harmonics("artificial_harmonic")
    with pytest.raises(ValueError):
        assert_distinct_from_harmonics("double_stop")


@pytest.mark.unsupported_extrapolation
def test_cello_multiphonic_not_auto_generalised_to_violin() -> None:
    mi = MultiphonicInstruction(instrument="vlc", source_reference="SRC_FALLOWFIELD_TEMPO_MULTIPHONICS")
    assert mi.instrument == "vlc"
    # No automatic violin activation field
    assert mi.model_dump().get("instrument") != "vln"


@pytest.mark.physical_plausibility
def test_synthetic_multiphonic_proxy_is_labelled_proxy() -> None:
    sig = generate_signal("two_component_multiphonic_proxy", seed=1)
    assert "proxy" in sig.metadata.get("proxy_warning", "").lower() or "proxy" in sig.kind


@pytest.mark.literature_bounded
def test_missing_chart_data_remain_unresolved() -> None:
    mi = MultiphonicInstruction(instrument="vlc")
    assert mi.touching_position_ratio is None
    assert mi.expected_pitch_components is None
    assert mi.principal_harmonic_components is None
