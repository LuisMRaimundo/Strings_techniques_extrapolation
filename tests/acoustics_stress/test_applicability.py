"""Applicability matrix stress tests."""

from __future__ import annotations

import pytest

from string_technique_model.applicability import ApplicabilityQuery, ApplicabilityStatus, resolve_applicability

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.unsupported_extrapolation
def test_mute_type_mismatch_not_applicable() -> None:
    param = {"applicable_mute_type": "heavy_practice"}
    result = resolve_applicability(
        param,
        ApplicabilityQuery(instrument="vln", technique="con_sordino", mute_type="orchestral"),
    )
    assert result.status == ApplicabilityStatus.not_applicable


@pytest.mark.domain_boundary
def test_contradictory_mute_mass_range_in_query() -> None:
    # Param must declare applicability dims so query contradiction checks run.
    result = resolve_applicability(
        {"applicable_dynamic": "mf"},
        ApplicabilityQuery(
            instrument="vln",
            technique="con_sordino",
            dynamic="mf",
            mute_mass_min=50.0,
            mute_mass_max=10.0,
        ),
    )
    assert result.status == ApplicabilityStatus.contradictory_metadata


@pytest.mark.unsupported_extrapolation
def test_absent_dynamic_not_defaulted_inside_resolver() -> None:
    param = {"applicable_dynamic": "pp"}
    result = resolve_applicability(
        param,
        ApplicabilityQuery(instrument="vln", technique="sul_ponticello", dynamic=None),
    )
    assert result.status == ApplicabilityStatus.insufficient_metadata


@pytest.mark.literature_bounded
def test_matched_when_dims_agree() -> None:
    param = {"applicable_dynamic": "mf", "applicable_metric_definition_id": "ewsd_v1"}
    result = resolve_applicability(
        param,
        ApplicabilityQuery(
            instrument="vln",
            technique="sul_tasto",
            dynamic="mf",
            target_metric_definition_id="ewsd_v1",
        ),
    )
    assert result.status == ApplicabilityStatus.matched


@pytest.mark.unsupported_extrapolation
def test_metric_mismatch() -> None:
    param = {"applicable_metric_definition_id": "ewsd_v1"}
    result = resolve_applicability(
        param,
        ApplicabilityQuery(
            instrument="vln",
            technique="sul_tasto",
            target_metric_definition_id="other_metric",
        ),
    )
    assert result.status == ApplicabilityStatus.not_applicable
