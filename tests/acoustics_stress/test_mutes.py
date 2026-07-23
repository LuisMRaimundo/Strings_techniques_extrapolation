"""Mute taxonomy and Evangelista scope stress tests."""

from __future__ import annotations

import pytest

from string_technique_model.production.models import MuteCategory, MuteInstruction
from string_technique_model.production.mute import normalize_mute_mass

pytestmark = pytest.mark.acoustics_stress

_DISTINCT = {"performance_mute", "light_practice", "heavy_practice", "heavy_practice_hotel"}


@pytest.mark.unit_consistency
def test_mute_mass_normalization_to_grams() -> None:
    g, raw, warnings = normalize_mute_mass("35 g")
    assert g == 35.0
    assert raw == "35 g"
    kg, _, _ = normalize_mute_mass("0.035 kg")
    assert kg == 35.0
    mg, _, _ = normalize_mute_mass("35000 mg")
    assert mg == 35.0


@pytest.mark.adversarial
def test_bare_mute_mass_not_silently_grams() -> None:
    g, _, warnings = normalize_mute_mass(35)
    assert g is None
    assert warnings


@pytest.mark.literature_bounded
@pytest.mark.benchmark
def test_benchmark_g_mute_categories_distinct() -> None:
    assert len(_DISTINCT) == len(set(_DISTINCT))
    for cat in _DISTINCT:
        assert cat in MuteCategory.__args__  # type: ignore[attr-defined]


@pytest.mark.unsupported_extrapolation
@pytest.mark.literature_bounded
def test_no_universal_mass_attenuation_api() -> None:
    assert not hasattr(normalize_mute_mass, "attenuation_db")
    mi = MuteInstruction(state="on", category="heavy_practice", mute_mass_g=40.0)
    dumped = mi.model_dump()
    assert "attenuation" not in dumped or dumped.get("attenuation") is None


@pytest.mark.unsupported_extrapolation
def test_violin_mute_fields_do_not_default_to_other_instruments() -> None:
    mi = MuteInstruction(state="on", category="performance_mute")
    assert mi.model_dump().get("instrument") is None
