"""User assumption isolation from literature evidence."""

from __future__ import annotations

import pytest

from string_technique_model.assumptions import get_user_assumption_registry, resolve_user_assumptions
from string_technique_model.prediction.modes import resolve_activate_user_assumptions

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.assumption_isolation
def test_evidence_only_mode_disables_assumptions() -> None:
    assert resolve_activate_user_assumptions("evidence_only") is False
    assert resolve_activate_user_assumptions("evidence_plus_user_assumptions") is True


@pytest.mark.assumption_isolation
@pytest.mark.benchmark
def test_benchmark_j_default_registry_empty_and_inactive() -> None:
    reg = get_user_assumption_registry()
    assert reg.literature_validated is False
    assert list(reg.assumptions) == []
    resolved = resolve_user_assumptions(
        context={"instrument": "vln", "technique": "sul_ponticello", "dynamic": "mf"},
        link="log",
        activation_enabled=True,
    )
    assert resolved == []


@pytest.mark.assumption_isolation
@pytest.mark.provenance
def test_assumption_registry_never_literature_validated() -> None:
    reg = get_user_assumption_registry()
    assert reg.literature_validated is False
    for a in reg.assumptions:
        assert a.literature_validated is False
