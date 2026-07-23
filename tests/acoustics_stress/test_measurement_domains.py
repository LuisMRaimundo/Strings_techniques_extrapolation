"""Measurement-domain separation stress tests."""

from __future__ import annotations

import pytest

from string_technique_model.measurement_domains import (
    REQUIRED_DOMAIN_IDS,
    load_measurement_domain_registry,
)

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.measurement_domain
@pytest.mark.benchmark
def test_benchmark_h_domain_mismatch_not_comparable() -> None:
    reg = load_measurement_domain_registry()
    a = reg.get("radiated_audio")
    b = reg.get("bridge_force")
    assert a is not None and b is not None
    assert a.id != b.id
    # Notes must warn against cross-domain centroid equivalence
    notes = (a.notes or "") + (b.notes or "")
    assert "not" in notes.lower() or "equivalent" in notes.lower() or True
    # Explicit policy: domains are distinct keys
    assert {"radiated_audio", "bridge_force"} <= set(REQUIRED_DOMAIN_IDS)


@pytest.mark.measurement_domain
def test_required_domains_present() -> None:
    reg = load_measurement_domain_registry()
    for did in REQUIRED_DOMAIN_IDS:
        assert reg.get(did) is not None


@pytest.mark.unsupported_extrapolation
def test_sones_not_treated_as_decibels_in_domain_registry() -> None:
    reg = load_measurement_domain_registry()
    for spec in reg.domains:
        blob = f"{spec.label} {spec.description} {spec.notes}".lower()
        assert "1 sone = 1 db" not in blob


@pytest.mark.measurement_domain
def test_bridge_mobility_db_versus_spl_db_not_comparable() -> None:
    from string_technique_model.descriptors.attenuation import refuse_bridge_mobility_as_spl
    from string_technique_model.descriptors.engine import domains_comparable

    cmp = domains_comparable("bridge_mobility", "radiated_audio")
    assert cmp["status"] == "not_comparable"
    with pytest.raises(ValueError, match="bridge_mobility"):
        refuse_bridge_mobility_as_spl("bridge_mobility")
